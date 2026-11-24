package warehouse;

import java.time.OffsetDateTime;
import java.time.Instant;
import java.util.*;

/** Single-process warehouse; quantities are whole boxes. */
public final class Warehouse {
    public abstract static class Entity {
        private final String id;
        protected Entity(String id) {
            if (id == null || id.isEmpty()) throw new IllegalArgumentException("Empty id");
            this.id = id;
        }
        public final String id() { return id; }
        public abstract Map<String,Object> snapshot();
    }
    public static final class Cell extends Entity {
        private final int capacity;
        private int used;
        public Cell(String id, int capacity) { super(id); positive(capacity); this.capacity=capacity; }
        public int free() { return capacity-used; }
        @Override public Map<String,Object> snapshot() { return map("capacity",capacity,"used",used); }
    }
    public static final class Lot extends Entity {
        private final String client, product, cell;
        private final Instant receivedAt;
        private final int seq;
        private int quantity, reserved;
        private boolean blocked;
        private Lot(String id,String client,String product,String cell,int quantity,Instant time,int seq) {
            super(id);this.client=client;this.product=product;this.cell=cell;
            this.quantity=quantity;this.receivedAt=time;this.seq=seq;
        }
        public int available() { return blocked ? 0 : quantity-reserved; }
        @Override public Map<String,Object> snapshot() { return map("client",client,"product",product,"cell",cell,
            "quantity",quantity,"reserved",reserved,"received_at",receivedAt.toString(),"seq",seq,"blocked",blocked); }
    }
    public record Allocation(String lot, int quantity) {
        public List<Object> values() { return List.of(lot,quantity); }
    }
    public enum Status { RESERVED, SHIPPED, CANCELLED }
    public static final class Order extends Entity {
        private final String client;
        private final Map<String,Integer> items;
        private final List<Allocation> plan;
        private Status status=Status.RESERVED;
        private Order(String id,String client,Map<String,Integer> items,List<Allocation> plan) {
            super(id);this.client=client;this.items=new LinkedHashMap<>(items);this.plan=List.copyOf(plan);
        }
        @Override public Map<String,Object> snapshot() { return map("client",client,"items",new LinkedHashMap<>(items),"status",status.name(),
            "plan",plan.stream().map(Allocation::values).toList()); }
    }
    public interface PlacementPolicy { String choose(Map<String,Cell> cells,int quantity); }
    public static final class BestFitPolicy implements PlacementPolicy {
        @Override public String choose(Map<String,Cell> cells,int quantity) {
            positive(quantity);
            return cells.values().stream().filter(c -> c.free()>=quantity)
                .min(Comparator.comparingInt(Cell::free).thenComparing(Cell::id))
                .orElseThrow(() -> new IllegalArgumentException("No cell fits")).id();
        }
    }
    public interface AllocationPolicy { List<Allocation> plan(Collection<Lot> lots,String client,String product,int quantity); }
    public static final class FifoPolicy implements AllocationPolicy {
        @Override public List<Allocation> plan(Collection<Lot> lots,String client,String product,int quantity) {
            positive(quantity);
            var candidates=lots.stream().filter(l -> l.client.equals(client) && l.product.equals(product) && l.available()>0)
                .sorted(Comparator.comparing((Lot l)->l.receivedAt).thenComparingInt(l->l.seq)).toList();
            var result=new ArrayList<Allocation>(); int remaining=quantity;
            for (Lot lot:candidates) {
                int take=Math.min(remaining,lot.available()); result.add(new Allocation(lot.id(),take)); remaining-=take;
                if (remaining==0) return result;
            }
            throw new IllegalArgumentException("Insufficient stock");
        }
    }
    private final Set<String> clients=new LinkedHashSet<>(List.of("C1","C2"));
    private final Set<String> products=new LinkedHashSet<>(List.of("P1","P2"));
    private final Map<String,Cell> cells=new LinkedHashMap<>();
    private final Map<String,Lot> lots=new LinkedHashMap<>();
    private final Map<String,Order> orders=new LinkedHashMap<>();
    private final List<Map<String,Object>> movements=new ArrayList<>();
    private final PlacementPolicy placement;
    private final AllocationPolicy allocation;
    private int nextSeq=1;
    public Warehouse() { this(new BestFitPolicy(),new FifoPolicy()); }
    public Warehouse(PlacementPolicy placement,AllocationPolicy allocation) {
        this.placement=Objects.requireNonNull(placement);this.allocation=Objects.requireNonNull(allocation);
        cells.put("A01",new Cell("A01",100));cells.put("A02",new Cell("A02",60));
    }
    public String receive(String id,String client,String product,int quantity,String timestamp) {
        positive(quantity);
        if (id==null || id.isEmpty() || lots.containsKey(id)) throw new IllegalArgumentException("Duplicate/empty lot");
        if (!clients.contains(client) || !products.contains(product)) throw new IllegalArgumentException("Unknown reference");
        final Instant time;
        try { time=OffsetDateTime.parse(timestamp).toInstant(); }
        catch (RuntimeException ex) { throw new IllegalArgumentException("Offset timestamp required",ex); }
        String cell=placement.choose(Collections.unmodifiableMap(cells),quantity);
        lots.put(id,new Lot(id,client,product,cell,quantity,time,nextSeq++)); cells.get(cell).used+=quantity;
        movements.add(map("type","RECEIVE","lot",id,"quantity",quantity,"order",null));return cell;
    }
    public List<Allocation> reserveOrder(String id,String client,Map<String,Integer> items) {
        if (id==null || id.isEmpty() || orders.containsKey(id)) throw new IllegalArgumentException("Duplicate/empty order");
        if (!clients.contains(client) || items==null || items.isEmpty()) throw new IllegalArgumentException("Invalid order");
        var plan=new ArrayList<Allocation>();
        for (var item:items.entrySet()) {
            if (!products.contains(item.getKey()) || item.getValue()==null) throw new IllegalArgumentException("Unknown product");
            plan.addAll(allocation.plan(Collections.unmodifiableCollection(lots.values()),client,item.getKey(),item.getValue()));
        }
        // Products occur once per map, so allocations of different lines cannot overlap.
        for (var a:plan) lots.get(a.lot()).reserved+=a.quantity();
        orders.put(id,new Order(id,client,items,plan));return List.copyOf(plan);
    }
    private Order reserved(String id) {
        Order o=orders.get(id);
        if (o==null || o.status!=Status.RESERVED) throw new IllegalArgumentException("Not reserved");return o;
    }
    public void shipOrder(String id) {
        Order o=reserved(id);
        for (var a:o.plan) { Lot l=lots.get(a.lot());
            if (l.blocked || l.reserved<a.quantity() || l.quantity<a.quantity()) throw new IllegalArgumentException("Blocked/invalid reserve"); }
        for (var a:o.plan) { Lot l=lots.get(a.lot()); l.quantity-=a.quantity();l.reserved-=a.quantity();cells.get(l.cell).used-=a.quantity();
            movements.add(map("type","SHIP","lot",l.id(),"quantity",-a.quantity(),"order",id)); }
        o.status=Status.SHIPPED;
    }
    public void cancelOrder(String id) {
        Order o=reserved(id);for (var a:o.plan) lots.get(a.lot()).reserved-=a.quantity();o.status=Status.CANCELLED;
    }
    public void setBlocked(String id,boolean blocked) {
        Lot l=lots.get(id);if(l==null)throw new IllegalArgumentException("Unknown lot");l.blocked=blocked;
    }
    public int availableStock(String client,String product) {
        return lots.values().stream().filter(l->l.client.equals(client)&&l.product.equals(product)).mapToInt(Lot::available).sum();
    }
    public void checkInvariants() {
        for (Lot l:lots.values()) {
            int active=orders.values().stream().filter(o->o.status==Status.RESERVED).flatMap(o->o.plan.stream())
                .filter(a->a.lot().equals(l.id())).mapToInt(Allocation::quantity).sum();
            int balance=movements.stream().filter(m->m.get("lot").equals(l.id())).mapToInt(m->(Integer)m.get("quantity")).sum();
            if(l.reserved<0||l.quantity<l.reserved||active!=l.reserved||balance!=l.quantity)throw new IllegalStateException("Lot invariant");
        }
        for(Cell c:cells.values()) {
            int used=lots.values().stream().filter(l->l.cell.equals(c.id())).mapToInt(l->l.quantity).sum();
            if(c.used!=used||c.used<0||c.free()<0)throw new IllegalStateException("Cell invariant");
        }
    }
    public Map<String,Object> snapshot() {
        var cs=new LinkedHashMap<String,Object>();cells.forEach((k,v)->cs.put(k,v.snapshot()));
        var ls=new LinkedHashMap<String,Object>();lots.forEach((k,v)->ls.put(k,v.snapshot()));
        var os=new LinkedHashMap<String,Object>();orders.forEach((k,v)->os.put(k,v.snapshot()));
        return map("clients",List.copyOf(clients),"products",List.copyOf(products),"cells",cs,"lots",ls,"orders",os,"movements",movements.stream().map(LinkedHashMap::new).toList(),"next_seq",nextSeq);
    }
    private static void positive(int q) { if(q<=0)throw new IllegalArgumentException("Positive integer required"); }
    static Map<String,Object> map(Object... pairs) {
        var m=new LinkedHashMap<String,Object>();for(int i=0;i<pairs.length;i+=2)m.put((String)pairs[i],pairs[i+1]);return m;
    }
}
