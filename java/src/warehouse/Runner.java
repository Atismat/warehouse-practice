package warehouse;
import java.nio.file.*;
import java.util.*;
/** Tab-separated operation runner. One JSON snapshot per operation. */
public final class Runner {
    private Runner() {}
    public static void main(String[] args) throws Exception {
        Warehouse w=new Warehouse();
        for(String line:Files.readAllLines(Path.of(args[0]))) {
            if(line.isBlank()||line.startsWith("#"))continue;
            String[] a=line.split("\t",-1);Object result=null;String status="OK";
            try {
                switch(a[0]) {
                    case "RESET" -> w=new Warehouse();
                    case "RECEIVE" -> result=w.receive(a[1],a[2],a[3],Integer.parseInt(a[4]),a[5]);
                    case "RESERVE" -> {
                        var items=new LinkedHashMap<String,Integer>();
                        if(a.length>3&&!a[3].isEmpty()) for(String pair:a[3].split(",")) {
                            String[] kv=pair.split(":",-1);
                            if(items.put(kv[0],Integer.parseInt(kv[1]))!=null)throw new IllegalArgumentException("Duplicate product");
                        }
                        result=w.reserveOrder(a[1],a[2],items).stream().map(Warehouse.Allocation::values).toList();
                    }
                    case "SHIP" -> w.shipOrder(a[1]);
                    case "CANCEL" -> w.cancelOrder(a[1]);
                    case "BLOCK" -> w.setBlocked(a[1],a[2].equals("1"));
                    case "AVAILABLE" -> result=w.availableStock(a[1],a[2]);
                    default -> throw new IllegalArgumentException("Unknown operation");
                }
            } catch(IllegalArgumentException ex) {status="ERROR";}
            w.checkInvariants();
            System.out.println(json(Warehouse.map("status",status,"result",result,"state",w.snapshot())));
        }
    }
    static String json(Object v) {
        if(v==null)return "null";
        if(v instanceof String s)return "\""+s.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r").replace("\t","\\t")+"\"";
        if(v instanceof Map<?,?> m) {
            var parts=new ArrayList<String>();m.forEach((k,x)->parts.add(json(k.toString())+":"+json(x)));return "{"+String.join(",",parts)+"}";
        }
        if(v instanceof Collection<?> c)return "["+String.join(",",c.stream().map(Runner::json).toList())+"]";
        return v.toString();
    }
}
