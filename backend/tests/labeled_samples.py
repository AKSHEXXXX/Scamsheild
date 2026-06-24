"""
Labeled test samples: 10 known scams + 10 known-legitimate messages.

Used by test_analyzer_split.py to verify tuning changes don't
break the scams-high / legit-low split.
"""

SCAM_SAMPLES = [
    {
        "label": "scam_parcel_arrest",
        "text": "Your parcel has been seized by customs. A case has been filed against you. Call immediately to avoid arrest.",
        "expected_verdict_in": ("high_risk", "suspicious"),
    },
    {
        "label": "scam_kyc_expiry",
        "text": "Your SBI account will be blocked in 24hrs. Update KYC now: https://sbi-update.con/verify or your account will be suspended.",
        "expected_verdict_in": ("high_risk", "suspicious"),
    },
    {
        "label": "scam_lottery_prize",
        "text": "CONGRATULATIONS! You won 25 lakhs in the Amazon Lucky Draw. Claim your prize now by paying a small processing fee. Limited time offer!",
        "expected_verdict_in": ("high_risk", "suspicious"),
    },
    {
        "label": "scam_income_tax_notice",
        "text": "Income Tax department: outstanding amount of Rs 12,500 pending. Immediate action required to avoid legal proceedings. Pay now at https://tax-refund.con.",
        "expected_verdict_in": ("high_risk", "suspicious"),
    },
    {
        "label": "scam_delivery_fee",
        "text": "Your package is held at our delivery center. Release fee of Rs 30 is required. Don't ignore this final notice. Pay via UPI: scammer@paytm.",
        "expected_verdict_in": ("high_risk", "suspicious"),
    },
    {
        "label": "scam_otp_fraud",
        "text": "Your debit card has been used for a transaction of Rs 49,999. If not you, call our toll-free helpline immediately to block. Do not share OTP.",
        "expected_verdict_in": ("high_risk", "suspicious"),
    },
    {
        "label": "scam_tech_support",
        "text": "Windows security alert: your computer has been compromised. Call our certified tech support team now for remote assistance. Act fast!",
        "expected_verdict_in": ("high_risk", "suspicious"),
    },
    {
        "label": "scam_phonepe_impersonation",
        "text": "PhonePe customer care: your account access is restricted due to suspicious login. Update and verify your details within 24 hours or your account will be terminated.",
        "expected_verdict_in": ("high_risk", "suspicious"),
    },
    {
        "label": "scam_courier_docket",
        "text": "Courier docket #IND9823 is pending customs clearance of Rs 2,400. Payment overdue. Final warning: legal action will be taken if not settled today.",
        "expected_verdict_in": ("high_risk", "suspicious"),
    },
    {
        "label": "scam_order_refund",
        "text": "Flipkart order #FK8765 refund of Rs 15,500 is pending due to failed transaction. Click here to claim: https://flipkart-refund.con. Limited time!",
        "expected_verdict_in": ("high_risk", "suspicious"),
    },
]

LEGIT_SAMPLES = [
    {
        "label": "legit_amazon_otp",
        "text": "Your Amazon OTP for login is 829341. Do not share this code with anyone.",
        "expected_verdict_in": ("low_risk",),
    },
    {
        "label": "legit_delivery_update",
        "text": "Your Flipkart order #OD1234567890 has been shipped. Track your delivery here: https://flipkart.com/track",
        "expected_verdict_in": ("low_risk",),
    },
    {
        "label": "legit_bank_alert",
        "text": "HDFC Bank: Rs 2,500 credited to savings account XX7890 on 12-Jun-2026. Available balance: Rs 18,432.",
        "expected_verdict_in": ("low_risk",),
    },
    {
        "label": "legit_meeting_invite",
        "text": "Reminder: Team standup tomorrow at 10 AM. Please confirm attendance. Meeting link will be shared separately.",
        "expected_verdict_in": ("low_risk",),
    },
    {
        "label": "legit_swiggy_order",
        "text": "Your Swiggy order from Pasta Central is confirmed! Expected delivery by 8:15 PM. Track live on the app.",
        "expected_verdict_in": ("low_risk",),
    },
    {
        "label": "legit_zomato_bill",
        "text": "Zomato order #ZO98765 delivered. Total: Rs 456. Rate your delivery experience!",
        "expected_verdict_in": ("low_risk",),
    },
    {
        "label": "legit_credit_card_statement",
        "text": "ICICI Credit Card: statement for June generated. Minimum due Rs 2,000 by 25-Jun. View bill online at icicibank.com",
        "expected_verdict_in": ("low_risk",),
    },
    {
        "label": "legit_app_update",
        "text": "Google Play: 3 app updates available. Tap to update WhatsApp, Instagram, and Truecaller.",
        "expected_verdict_in": ("low_risk",),
    },
    {
        "label": "legit_flight_booking",
        "text": "Your IndiGo flight 6E-2345 on 15-Jun DEL to BOM is confirmed. Web check-in opens 48hrs before departure.",
        "expected_verdict_in": ("low_risk",),
    },
    {
        "label": "legit_social_notification",
        "text": "John Doe liked your photo. You have 5 new notifications on Instagram.",
        "expected_verdict_in": ("low_risk",),
    },
]
