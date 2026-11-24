PRAGMA foreign_keys = ON;
CREATE TABLE client (client_id TEXT PRIMARY KEY NOT NULL CHECK(length(client_id)>0)) STRICT;
CREATE TABLE product (product_id TEXT PRIMARY KEY NOT NULL CHECK(length(product_id)>0), unit TEXT NOT NULL DEFAULT 'box' CHECK(unit='box')) STRICT;
CREATE TABLE warehouse_cell (cell_id TEXT PRIMARY KEY NOT NULL CHECK(length(cell_id)>0), capacity INTEGER NOT NULL CHECK(capacity>0)) STRICT;
CREATE TABLE lot (
 lot_id TEXT PRIMARY KEY NOT NULL CHECK(length(lot_id)>0), client_id TEXT NOT NULL REFERENCES client,
 product_id TEXT NOT NULL REFERENCES product, cell_id TEXT NOT NULL REFERENCES warehouse_cell,
 quantity INTEGER NOT NULL CHECK(quantity>=0),
 received_at TEXT NOT NULL CHECK(length(received_at)>=20 AND substr(received_at,11,1)='T' AND julianday(received_at) IS NOT NULL AND (substr(received_at,-1)='Z' OR substr(received_at,-6,1) IN ('+','-'))),
 seq INTEGER NOT NULL UNIQUE CHECK(seq>0), blocked INTEGER NOT NULL CHECK(blocked IN (0,1)),
 UNIQUE(lot_id,client_id,product_id)
) STRICT;
CREATE TABLE outbound_order (
 order_id TEXT PRIMARY KEY NOT NULL CHECK(length(order_id)>0), client_id TEXT NOT NULL REFERENCES client,
 status TEXT NOT NULL CHECK(status IN ('RESERVED','SHIPPED','CANCELLED')), UNIQUE(order_id,client_id)
) STRICT;
CREATE TABLE order_line (
 order_id TEXT NOT NULL, product_id TEXT NOT NULL REFERENCES product, client_id TEXT NOT NULL,
 quantity INTEGER NOT NULL CHECK(quantity>0), line_no INTEGER NOT NULL CHECK(line_no>0),
 PRIMARY KEY(order_id,product_id), UNIQUE(order_id,line_no), UNIQUE(order_id,product_id,client_id),
 FOREIGN KEY(order_id,client_id) REFERENCES outbound_order(order_id,client_id)
) STRICT;
CREATE TABLE reservation (
 order_id TEXT NOT NULL, product_id TEXT NOT NULL, client_id TEXT NOT NULL, lot_id TEXT NOT NULL,
 quantity INTEGER NOT NULL CHECK(quantity>0), position INTEGER NOT NULL CHECK(position>0),
 PRIMARY KEY(order_id,lot_id), UNIQUE(order_id,position),
 FOREIGN KEY(order_id,product_id,client_id) REFERENCES order_line(order_id,product_id,client_id),
 FOREIGN KEY(lot_id,client_id,product_id) REFERENCES lot(lot_id,client_id,product_id)
) STRICT;
CREATE TABLE movement (
 movement_id INTEGER PRIMARY KEY CHECK(movement_id>0), lot_id TEXT NOT NULL REFERENCES lot,
 type TEXT NOT NULL CHECK(type IN ('RECEIVE','SHIP')), quantity INTEGER NOT NULL,
 order_id TEXT REFERENCES outbound_order,
 CHECK((type='RECEIVE' AND quantity>0 AND order_id IS NULL) OR (type='SHIP' AND quantity<0 AND order_id IS NOT NULL))
) STRICT;
CREATE INDEX lot_fifo ON lot(client_id,product_id,blocked,seq);
-- Time ordering stays in the domain code: ISO offsets must be compared as instants.
CREATE VIEW lot_balance AS
 SELECT l.*, COALESCE((SELECT SUM(r.quantity) FROM reservation r JOIN outbound_order o USING(order_id)
 WHERE r.lot_id=l.lot_id AND o.status='RESERVED'),0) AS reserved FROM lot l;
CREATE VIEW cell_balance AS
 SELECT c.*, COALESCE((SELECT SUM(l.quantity) FROM lot l WHERE l.cell_id=c.cell_id),0) AS used FROM warehouse_cell c;
CREATE TRIGGER lot_capacity_insert BEFORE INSERT ON lot BEGIN
 SELECT CASE WHEN NEW.quantity + COALESCE((SELECT SUM(quantity) FROM lot WHERE cell_id=NEW.cell_id),0)
 > (SELECT capacity FROM warehouse_cell WHERE cell_id=NEW.cell_id) THEN RAISE(ABORT,'cell capacity exceeded') END;
END;
CREATE TRIGGER lot_capacity_update BEFORE UPDATE OF quantity,cell_id ON lot BEGIN
 SELECT CASE WHEN NEW.quantity + COALESCE((SELECT SUM(quantity) FROM lot WHERE cell_id=NEW.cell_id AND lot_id<>OLD.lot_id),0)
 > (SELECT capacity FROM warehouse_cell WHERE cell_id=NEW.cell_id) THEN RAISE(ABORT,'cell capacity exceeded') END;
END;
CREATE TRIGGER cell_capacity_update BEFORE UPDATE OF capacity ON warehouse_cell BEGIN
 SELECT CASE WHEN NEW.capacity < COALESCE((SELECT SUM(quantity) FROM lot WHERE cell_id=OLD.cell_id),0)
 THEN RAISE(ABORT,'cell capacity below occupancy') END;
END;
