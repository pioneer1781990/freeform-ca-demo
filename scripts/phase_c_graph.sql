-- BQ Property Graph: Customer -> Product -> DistributionCenter

-- Primary keys (unenforced) for graph optimization
ALTER TABLE `new-project-495419.cymbal_retail.users`                 ADD PRIMARY KEY (id) NOT ENFORCED;
ALTER TABLE `new-project-495419.cymbal_retail.products`              ADD PRIMARY KEY (id) NOT ENFORCED;
ALTER TABLE `new-project-495419.cymbal_retail.distribution_centers`  ADD PRIMARY KEY (id) NOT ENFORCED;

-- Edge views (clean FK-to-PK)
CREATE OR REPLACE VIEW `new-project-495419.cymbal_retail.purchase_edges` AS
SELECT DISTINCT user_id AS customer_id, product_id
FROM `new-project-495419.cymbal_retail.order_items`
WHERE status NOT IN ('Cancelled');

CREATE OR REPLACE VIEW `new-project-495419.cymbal_retail.stocking_edges` AS
SELECT DISTINCT
  product_id,
  product_distribution_center_id AS dc_id
FROM `new-project-495419.cymbal_retail.inventory_items`
WHERE product_distribution_center_id IS NOT NULL;

-- Property graph
CREATE OR REPLACE PROPERTY GRAPH `new-project-495419.cymbal_retail.cymbal_retail_graph`
  NODE TABLES (
    `new-project-495419.cymbal_retail.users` AS Customer
      KEY (id)
      LABEL Customer
      PROPERTIES (id, first_name, last_name, age, gender, country, city, traffic_source),
    `new-project-495419.cymbal_retail.products` AS Product
      KEY (id)
      LABEL Product
      PROPERTIES (id, name, brand, category, department, retail_price, cost),
    `new-project-495419.cymbal_retail.distribution_centers` AS DC
      KEY (id)
      LABEL DistributionCenter
      PROPERTIES (id, name, latitude, longitude)
  )
  EDGE TABLES (
    `new-project-495419.cymbal_retail.purchase_edges` AS Purchased
      KEY (customer_id, product_id)
      SOURCE KEY (customer_id) REFERENCES Customer (id)
      DESTINATION KEY (product_id) REFERENCES Product (id)
      LABEL Purchased,
    `new-project-495419.cymbal_retail.stocking_edges` AS StockedAt
      KEY (product_id, dc_id)
      SOURCE KEY (product_id) REFERENCES Product (id)
      DESTINATION KEY (dc_id) REFERENCES DC (id)
      LABEL StockedAt
  );
