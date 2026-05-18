-- Olist label + descriptions
ALTER TABLE `new-project-495419.cymbal_retail.customer_reviews` SET OPTIONS (
  labels = [('agent_ready','true')],
  description = 'Customer satisfaction reviews from Cymbal marketplace. Scores 1-5. Comments in Portuguese. review_comment_message contains free-text feedback.'
);
ALTER TABLE `new-project-495419.cymbal_retail.customer_payments` SET OPTIONS (
  labels = [('agent_ready','true')]
);
ALTER TABLE `new-project-495419.cymbal_retail.marketplace_orders` SET OPTIONS (
  labels = [('agent_ready','true')],
  description = 'Marketplace order lifecycle. Key timestamps: order_purchase_timestamp, order_approved_at, order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date. Late delivery = delivered > estimated.'
);
ALTER TABLE `new-project-495419.cymbal_retail.marketplace_customers` SET OPTIONS (
  labels = [('agent_ready','true')]
);
ALTER TABLE `new-project-495419.cymbal_retail.marketplace_sellers` SET OPTIONS (
  labels = [('agent_ready','true')]
);

ALTER TABLE `new-project-495419.cymbal_retail.customer_reviews`
ALTER COLUMN review_score SET OPTIONS (description = 'Customer satisfaction score: 1 (worst) to 5 (best). Satisfied >= 4, Dissatisfied <= 2.');

ALTER TABLE `new-project-495419.cymbal_retail.customer_reviews`
ALTER COLUMN review_comment_message SET OPTIONS (description = 'Free-text review comment in Portuguese. May be NULL. Contains customer sentiment about delivery, product quality, etc.');
