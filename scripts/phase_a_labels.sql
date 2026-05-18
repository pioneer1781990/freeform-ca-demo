-- agent_ready: true on all production tables
ALTER TABLE `new-project-495419.cymbal_retail.orders` SET OPTIONS (labels = [('agent_ready', 'true')]);
ALTER TABLE `new-project-495419.cymbal_retail.order_items` SET OPTIONS (labels = [('agent_ready', 'true')]);
ALTER TABLE `new-project-495419.cymbal_retail.products` SET OPTIONS (labels = [('agent_ready', 'true')]);
ALTER TABLE `new-project-495419.cymbal_retail.users` SET OPTIONS (labels = [('agent_ready', 'true')]);
ALTER TABLE `new-project-495419.cymbal_retail.distribution_centers` SET OPTIONS (labels = [('agent_ready', 'true')]);
ALTER TABLE `new-project-495419.cymbal_retail.inventory_items` SET OPTIONS (labels = [('agent_ready', 'true')]);
ALTER TABLE `new-project-495419.cymbal_retail.inventory_snapshots` SET OPTIONS (labels = [('agent_ready', 'true')]);
ALTER TABLE `new-project-495419.cymbal_retail.supplier_catalog` SET OPTIONS (labels = [('agent_ready', 'true')]);
ALTER TABLE `new-project-495419.cymbal_retail.support_tickets` SET OPTIONS (labels = [('agent_ready', 'true')]);
ALTER TABLE `new-project-495419.cymbal_retail.return_claims` SET OPTIONS (labels = [('agent_ready', 'true')]);

-- agent_ready: false on dev/staging tables (+ descriptions)
ALTER TABLE `new-project-495419.cymbal_retail.orders_staging` SET OPTIONS (
  labels = [('agent_ready', 'false')],
  description = 'STAGING: Partial order data for ETL testing. DO NOT USE FOR ANALYTICS.'
);
ALTER TABLE `new-project-495419.cymbal_retail.products_dev` SET OPTIONS (
  labels = [('agent_ready', 'false')],
  description = 'DEV: Product catalog subset for development. Schema differs from production.'
);
ALTER TABLE `new-project-495419.cymbal_retail.user_events_raw` SET OPTIONS (
  labels = [('agent_ready', 'false')],
  description = 'RAW: Unprocessed clickstream. No deduplication or session stitching.'
);
ALTER TABLE `new-project-495419.cymbal_retail.tmp_analysis_20260510` SET OPTIONS (
  labels = [('agent_ready', 'false')]
);
