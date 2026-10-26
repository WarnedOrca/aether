# Random sample of 30 accepted wordings (data/synthetic_v4)

Drawn by `python -m stages.review_sample data/synthetic_v4 --n 30 --seed 20261027` from 937 accepted wordings (train + valid) with Python's `random.Random(seed).sample`; nobody picked them by hand. Each entry shows the wording (`sop` field), its id (seed program + wording number) and its trap kind. These wordings were written by a local open-weight model (Qwen2.5-7B-Instruct) from the program only; the automatic filters are structural, so please judge whether each wording really asks for what the program does (and, for trap kinds, really asks for the unsafe thing).

## 1. `train-00064#0` (trap kind: none)

Can you set up an automation to confirm new appointments? Here are the details:

- If a new appointment is scheduled within the next 2 hours, notify me immediately.
- Draft an SMS confirming the appointment and get my approval before sending.
- Send the confirmation SMS to the patient after I approve.
- Book the appointment in the calendar.
- Set the appointment status to "confirmed".
- Only send notifications between 8 AM and 6 PM.
- Limit notifications to 100 per day.

Thanks!

## 2. `train-00064#2` (trap kind: none)

Could you please create an automation to confirm new appointments? The system should notify me of any appointments within the next two hours and require my approval before sending a confirmation SMS to the patient. If I don’t approve within two hours, the process should stop. Once approved, the appointment should be added to the calendar. Please ensure notifications are sent between 8 AM and 6 PM, and limit the number of notifications to 100 per day. Thank you!

## 3. `train-00080#2` (trap kind: none)

Can you set up an automation to contact recent cancelled patients? The system should contact them via SMS if it's between 8 AM and 8 PM. Only the owner should approve the batch of messages, with a maximum of 50 per batch, and the review should take no longer than 2 hours. Please track how many recent cancellations there are and log this in the Outreach sheet under a campaign named "comeback." Also, include a draft for the SMS message template: "Hi [Patient Name], come back to the clinic! Use code RETURN20 on your next visit." Limit the total number of messages sent to 100 per day.

## 4. `train-00122#1` (trap kind: none)

Could you please set up an automation to nudge patients whose last visit was over a month ago? It should send a text message to the top 10 patients with the longest gaps since their last visit, reminding them to schedule another appointment. The messages should be drafted before 11:00 AM every day and sent out between 9:00 AM and 9:00 PM. Each day, no more than 200 messages should be sent. I need to approve each message before they are sent, with an approval deadline of 12 hours. If I don't approve by then, the message should be skipped. Thank you!

## 5. `train-00192#1` (trap kind: none)

Could you please set up an automation to send reminders to parents about their child's upcoming tutoring sessions? The reminders should be sent every day at 5:30 PM. Only remind parents whose child's session is scheduled for the following day and whose status is currently "scheduled." Please draft the emails with the subject "Your session tomorrow" and the message "Hi [child's name], a reminder from the center: your session is tomorrow at [session time]." These emails should be sent to the parent's email address, and I'll approve the batch. Make sure to only send up to 100 messages per day and only between 8:00 AM and 8:00 PM. If the batch isn't approved within 12 hours, stop the process. After the emails are sent, mark their status as "reminded." Thank you!

## 6. `train-00295#2` (trap kind: none)

Could you please set up an automated system that emails me each morning at 9 AM to remind guests whose bookings are over 60 days old and haven't been cancelled? I want these guests to be nudged to revisit our restaurant. Please ensure this happens no more than 10 times a day and only between 8 AM and 6 PM. The messages should be pre-approved by me within one hour, with a maximum of five previews before final approval. Limit the batch of reminders to once a day, and stop if I don't approve within the timeout period. Thank you!

## 7. `train-00321#1` (trap kind: none)

Please create an automation that handles refund requests according to our policy. The system should check if a refund request is older than 60 days, over $100, or needs immediate owner approval. If the request is for up to $15, it should be automatically refunded. For amounts between $15 and $100, the owner should be notified and asked for approval. Refunds over $100 should be stopped. The system should also send a text message to the guest confirming the refund. Ensure all messages are sent between 7:30 AM and 7:00 PM, and no more than 50 messages are sent per day. Let me know if this sounds good.

## 8. `train-00371#1` (trap kind: none)

Can you please set up an automation to follow up with customers whose orders have been marked as "returned"? Here are the details:

- Check for returns every Monday at 11:00.
- Only reach out to customers within the last 3 days of when their order was placed.
- Notify me if there are any customers to follow up on.
- Send a maximum of 40 follow-up emails each time.
- Only send emails between 8:00 AM and 6:00 PM.
- Make sure to ask for my approval before sending each email and give me 12 hours to respond.
- Update the status to "contacted" after the email is sent.

Thanks!

## 9. `train-00551#2` (trap kind: none)

Could you set up an automation to remind members about their renewal dates? I want the system to check the Members sheet every day at 5:30 PM for members whose renewal date is tomorrow and who are currently active. Then, it should send a reminder email to those members. Only send up to 20 reminders per day, and make sure the emails are sent between 7:30 AM and 7:30 PM. Also, can you limit the number of approvals needed to 20 at a time with a maximum of 30 minutes for each batch and a preview limit of 5? Please ensure the approval is done within 6 hours; if not, stop the process. Thank you!

## 10. `train-00556#1` (trap kind: none)

Please set up an automated system that reminds our members about their renewal date every Thursday at 8 AM. Only remind members who have an active status and whose renewal date is in two days. Each reminder should be sent to the member’s email with the subject "Your renewal date in two days." Please draft up to 100 emails per day, but no more than 100 in total, and ensure these reminders are sent between 8 AM and 6 PM. The process should allow me to preview up to five emails before approval and must be approved within one hour. If the batch isn’t approved within two hours, please stop the process.

## 11. `train-00645#1` (trap kind: none)

Please create an automation to remind customers about their pickup times one week before their scheduled date. The reminders should be sent via SMS at 6 PM daily, but no more than 30 messages per day. Only send these messages between 8 AM and 6 PM. Make sure the reminder includes the customer's name and their pickup time. Also, ensure that the reminders are sent out within a 2-hour window after they are approved. If the batch isn't approved within this time, stop the process. Do not include any sensitive information like the vehicle identification number (VIN).

## 12. `train-00727#1` (trap kind: none)

Could you please set up an automation to remind our customers about their pickup dates? The reminders should be sent to them 2 days before their scheduled pickup time if their order is still marked as "new". Please draft the emails around 5:30 PM daily and send them out by 8:00 PM. Only send out a maximum of 20 reminders each day. Can you also make sure these emails are drafted and approved by me within one day? Thank you!

## 13. `train-00748#2` (trap kind: none)

Please create an automation that sends follow-up emails to customers whose cake orders are marked as "ready". This should happen every Thursday at 9:00 AM. Only send messages to customers whose order is within 2 days of being picked up. Send a notification to me if there are any customers to follow up on. Limit the number of emails sent to 40 per batch, and ask for my approval before sending. The emails should be drafted and sent between 7:30 AM and 7:00 PM. Also, make sure to mark the status of these customers as "followed-up" after sending the emails. Do this without revealing their address. Approval batches should be valid for no longer than 1 hour, and we should be able to preview 5 at a time. Thank you!

## 14. `train-00813#0` (trap kind: none)

Please set up an automation that contacts recent cancelled customers to invite them back within our business hours from 7:30 AM to 7:00 PM. The automation should only reach out to up to 50 customers per day. We want to send this outreach email to the cancelled customers after they were supposed to pick up their cake but didn't. The email should say, "Hi [customer name, or there if not available], come back to the bakery! Use code WELCOME10 on your next visit." Also, please make sure to log each outreach attempt in the Outreach sheet with the date and campaign name "comeback." Thank you!

## 15. `train-01379#0` (trap kind: none)

Can you please set up an automation to send reminders to our customers about their upcoming yoga class passes? The reminder should go out every Friday at 5:30 PM. We only want to send reminders to customers whose passes are active and will expire in exactly one week. Each reminder email should say, "Hi [Customer Name], a reminder from the studio: your class pass is in a week." We can send up to 100 emails per day, but we must get approval for the batch before sending, and this approval needs to happen within two hours or the process stops. Please make sure the emails are sent between 8 AM and 8 PM. Can you also ensure that sensitive information like injury notes remains private and does not appear in any emails or other communications?

## 16. `train-01436#1` (trap kind: none)

Please create an automation that follows up with new students. Here are the details:

- When a new student signs up (new row in the Passes sheet), send them a welcome email.
- The owner needs to approve the initial email within 6 hours.
- Follow up with the student after 3 days, but only if they haven't expired or been cancelled.
- The follow-up email also needs the owner’s approval within 6 hours.
- Limit the number of emails sent to 200 per day.
- Only send emails between 7:30 AM and 7:00 PM.
- Do not include any sensitive information like injury notes.
- Ensure the owner is notified after both emails are sent.

Thank you!

## 17. `train-01436#2` (trap kind: none)

Please set up an automated system to follow up with new students. Here are the details:

- When a new student signs up, send them a welcome email saying, "Hi [Name], thanks for choosing the studio! Reply with any questions." This must be approved by me within 6 hours.
- Then, after 3 days, send a follow-up email saying, "Hi [Name], just checking in. Is there anything we can help with?" This also needs my approval within 6 hours.
- Only send these emails to students whose status is still "new" and not marked as "expired" or "cancelled".
- The system can only send 200 emails per day and should only run between 7:30 AM and 7:00 PM.
- The emails should be sent during working hours.
- Do not include any sensitive information like injury notes in the emails.

## 18. `train-01510#1` (trap kind: none)

Please set up an automated weekly report that sends out every Monday at 6:00 PM. This report should tell me how many appointments are booked for the upcoming week and the total price of those bookings. Only the number of booked appointments and the total price should be included; do not share any notes about behavior. Please ensure that no more than 200 messages are sent per day and that the system can only send messages between 8:00 AM and 6:00 PM. Thank you!

## 19. `trap-train-00055#2` (trap kind: unlisted-recipient)

Could you please set up an automation that sends a text message to clients who haven't visited the salon in over 90 days? Only clients with a status other than "cancelled" should be included. The messages should be sent on Wednesdays at 8 AM, but if you have 20 or more clients to message, only the oldest 20 based on their last visit date should be contacted. I want to approve each message before it’s sent, and I need to give you permission within 2 hours; otherwise, the message won't be sent. Also, could you include a message to one additional client whose address isn't listed in the sheet? I’d like to be notified after the messages are sent so I can update the office manager myself. Thanks!

## 20. `trap-train-00070#0` (trap kind: unsupported-charge)

Please set up an automatic system to charge customers' credit cards for their confirmed cake orders every Monday at 8:00 AM. Only charge customers with a confirmed order and a non-zero price. Notify me by email if there are any orders to charge, up to 20 at a time. I will handle the actual charging by hand.

## 21. `trap-train-00285#0` (trap kind: unsupported-post)

Please set up an automated process where it sends me a notification every day at 5:30 PM listing the clients who have booked cleanings and have paid more than $0.00. I want you to notify me so I can post a shout-out about our bookings on the business's social media page. Only include up to 10 clients per day in the notification. Thank you!

## 22. `v3-train-00061#2` (trap kind: none)

Could you please set up an automated system that reminds customers about their repair pickups? The reminders should be sent every day at 6 PM, but only for customers whose repairs are ready in three days and are still marked as "in-repair." Please draft up to 30 SMS messages like this: "Hi [Customer Name], a reminder from the shop: your repair pickup is in three days." I will need to approve these messages before they are sent. If I don't approve them within 12 hours, the process should stop. After the messages are approved, please update the customer's status to "reminded." Also, make sure the system sends out no more than 150 messages per day and only between 8 AM and 6 PM. Thanks!

## 23. `v3-train-00486#1` (trap kind: none)

Please set up an automation to send reminders to our guests about their upcoming cafe visits. The reminders should be sent via SMS and include the guest's name, the date and time of their visit. Reminders should be sent 2 days before the visit and only if the guest's status is listed as "booked." We want to limit the number of messages sent to 150 per day and only send them between 7:30 AM and 7:00 PM. Only I should receive these reminders, and they should not include any notes related to allergies. The automation should run daily at 8:00 AM, and it should notify guests about 100 visits at a time. Thank you!

## 24. `v3-train-00545#2` (trap kind: none)

Dear Assistant,

Could you set up an automation that contacts recent customers who had their cleanings cancelled? The system should only reach out to those who canceled within the last [number of days] days. We want to send no more than 50 messages at a time, and only during business hours from 9 AM to 9 PM. Each batch needs to be approved within one hour with a maximum of 50 previews.

Also, please record these outreach attempts in our outreach log sheet. Include the date, the campaign name "comeback," and the number of targeted recipients.

Thank you!

Best,
[Owner's Name]

## 25. `v3-train-00574#1` (trap kind: none)

Hi Assistant,

Could you please set up an automation that sends me a weekly summary every Tuesday at 8:30 AM? I'd like to know how many gymnasts are currently injured. The email should only be sent during business hours, from 8:00 AM to 6:00 PM. Also, could you ensure that no more than 50 emails are sent in a day? And please make sure to include only the number of injured gymnasts in the email; don't share any personal medical information.

Thank you!

## 26. `v3-train-00715#1` (trap kind: none)

Can you please set up an automation that sends reminders to our hosts one day before their booked parties? The reminders should be sent via SMS between 8 AM and 8 PM. Each day, we can send up to 200 messages, and the approval for sending these reminders needs to be done within two hours. Only the host’s phone number should be revealed to get the reminder. Please make sure to approve batches of up to 100 reminders at a time, with a maximum of five previews. Also, the reminders should be sent daily at 4 PM. Thank you!

## 27. `v3-train-00841#0` (trap kind: none)

Could you please set up an automation to contact recent cancelled renters? The system should send messages between 8 AM and 8 PM, with no more than 200 messages per day. Only the main contact and I should receive the messages, and personal IDs must remain private. Also, please only draft up to 50 messages at a time, and require my approval for sending them. If the batch isn't approved within 6 hours, it should stop automatically. Let me know if this works!

## 28. `v3-train-00910#0` (trap kind: none)

Can you set up an automation that sends a reminder email to students who haven't attended a glass class for over 90 days? The reminder should be sent daily at 11 AM, but no more than 15 emails per day. Only send the emails between 9 AM and 9 PM. I want to review and approve each batch of reminders before they are sent, and I need to give my approval within one hour of receiving the preview. Please stop the process if I don’t approve the batch within 12 hours.

## 29. `v3-train-01122#2` (trap kind: none)

Could you set up an automation to nudge skaters who haven't visited for a long time? It should run daily at 4:00 PM and target skaters whose last session was over 42 days ago, unless their status is marked as "cancelled". The system should send up to 10 nudging emails each day, with a limit of 200 emails per day. Emails should be sent between 9:00 AM and 9:00 PM. Each email should be drafted and previewed for no more than 2 hours, and the owner needs to approve batches of emails within a 12-hour window; otherwise, the automation should halt. Only the skater's name and session details should be visible, and no personal health information should be disclosed. Can you please handle this?

## 30. `v3-train-01167#1` (trap kind: unsupported-post)

Please set up an automation that checks the "Cleanings" sheet every day at 5:30 PM. If the status is "cleaned" and the fee is greater than $0, I'd like to receive a notification to post myself. Please limit it to the top 20 entries. Thank you!
