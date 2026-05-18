-- ObjectRef tables: structured rows pointing to GCS objects

-- 1. Review docs (Portuguese review text in GCS)
CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.review_docs` AS
SELECT
  review_id,
  OBJ.FETCH_METADATA(
    OBJ.MAKE_REF(
      CONCAT('gs://new-project-495419-cymbal-retail/reviews/', review_id, '.txt'),
      'us.cymbal-gcs-conn'
    )
  ) AS doc_ref
FROM `new-project-495419.cymbal_retail.customer_reviews`
WHERE review_comment_message IS NOT NULL
  AND LENGTH(review_comment_message) > 30
LIMIT 30;

ALTER TABLE `new-project-495419.cymbal_retail.review_docs` SET OPTIONS (
  labels = [('agent_ready','true')],
  description = 'ObjectRef to review text files in GCS (gs://.../reviews/). Companion to customer_reviews table. doc_ref is a STRUCT pointing to the GCS object; use OBJ.GET_ACCESS_URL or OBJ.READ to access content.'
);

-- 2. Support ticket docs (email/chat/phone transcripts in GCS)
CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.support_ticket_docs` (
  ticket_id STRING,
  channel STRING,
  doc_ref STRUCT<uri STRING, version STRING, authorizer STRING, details JSON>
);

INSERT INTO `new-project-495419.cymbal_retail.support_ticket_docs`
VALUES
  ('TKT001','email',OBJ.FETCH_METADATA(OBJ.MAKE_REF('gs://new-project-495419-cymbal-retail/support/TKT001_email.txt','us.cymbal-gcs-conn'))),
  ('TKT002','chat', OBJ.FETCH_METADATA(OBJ.MAKE_REF('gs://new-project-495419-cymbal-retail/support/TKT002_chat.txt','us.cymbal-gcs-conn'))),
  ('TKT003','phone',OBJ.FETCH_METADATA(OBJ.MAKE_REF('gs://new-project-495419-cymbal-retail/support/TKT003_phone.txt','us.cymbal-gcs-conn'))),
  ('TKT004','email',OBJ.FETCH_METADATA(OBJ.MAKE_REF('gs://new-project-495419-cymbal-retail/support/TKT004_email.txt','us.cymbal-gcs-conn'))),
  ('TKT005','chat', OBJ.FETCH_METADATA(OBJ.MAKE_REF('gs://new-project-495419-cymbal-retail/support/TKT005_chat.txt','us.cymbal-gcs-conn'))),
  ('TKT006','email',OBJ.FETCH_METADATA(OBJ.MAKE_REF('gs://new-project-495419-cymbal-retail/support/TKT006_email.txt','us.cymbal-gcs-conn'))),
  ('TKT007','phone',OBJ.FETCH_METADATA(OBJ.MAKE_REF('gs://new-project-495419-cymbal-retail/support/TKT007_phone.txt','us.cymbal-gcs-conn'))),
  ('TKT008','email',OBJ.FETCH_METADATA(OBJ.MAKE_REF('gs://new-project-495419-cymbal-retail/support/TKT008_email.txt','us.cymbal-gcs-conn')));

ALTER TABLE `new-project-495419.cymbal_retail.support_ticket_docs` SET OPTIONS (
  labels = [('agent_ready','true')],
  description = 'ObjectRef to support ticket transcripts in GCS. Companion to support_tickets table. Each ticket has the structured row + an unstructured email/chat/phone transcript referenced via doc_ref.'
);

-- 3. Return claim evidence
CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.return_evidence_docs` (
  claim_id STRING,
  evidence_ref STRUCT<uri STRING, version STRING, authorizer STRING, details JSON>
);

INSERT INTO `new-project-495419.cymbal_retail.return_evidence_docs`
VALUES
  ('CLM001', OBJ.FETCH_METADATA(OBJ.MAKE_REF('gs://new-project-495419-cymbal-retail/return_evidence/CLM001.txt','us.cymbal-gcs-conn'))),
  ('CLM002', OBJ.FETCH_METADATA(OBJ.MAKE_REF('gs://new-project-495419-cymbal-retail/return_evidence/CLM002.txt','us.cymbal-gcs-conn')));

ALTER TABLE `new-project-495419.cymbal_retail.return_evidence_docs` SET OPTIONS (
  labels = [('agent_ready','true')],
  description = 'ObjectRef to customer-uploaded return evidence files in GCS. Companion to return_claims table.'
);

-- 4. Product images
CREATE OR REPLACE TABLE `new-project-495419.cymbal_retail.product_images` AS
SELECT
  id AS product_id,
  OBJ.FETCH_METADATA(
    OBJ.MAKE_REF(
      CONCAT('gs://new-project-495419-cymbal-retail/product_images/prod_', CAST(id AS STRING), '.png'),
      'us.cymbal-gcs-conn'
    )
  ) AS image_ref
FROM `new-project-495419.cymbal_retail.products`
LIMIT 8;

ALTER TABLE `new-project-495419.cymbal_retail.product_images` SET OPTIONS (
  labels = [('agent_ready','true')],
  description = 'ObjectRef to product images in GCS. Joins to products table on product_id.'
);
