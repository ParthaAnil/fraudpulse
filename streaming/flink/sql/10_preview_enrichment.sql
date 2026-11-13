-- Preview: 10 live payments, each with the user's and merchant's details at that moment.
-- Run with: make flink-preview
SELECT transaction_id, user_id, city, payment_time,
       user_home_city, user_kyc_level, merchant_category, merchant_status
FROM enriched_payments
LIMIT 10;
