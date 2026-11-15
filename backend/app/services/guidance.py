from app.schemas import EvonAnalysis, GuidanceItem


def select_guidance(analysis: EvonAnalysis) -> tuple[str, str, str, list[GuidanceItem]]:
    """Deterministic protective actions; model output never chooses official destinations."""
    actions: list[GuidanceItem] = []

    if analysis.financial_loss_reported:
        actions.extend([
            GuidanceItem(
                title="Contact your bank immediately",
                detail="Use the official number or app you obtain independently. Report the unauthorised transaction and ask the bank to secure the affected account and payment instruments.",
                urgency="urgent",
            ),
            GuidanceItem(
                title="Call India's cyber-fraud helpline",
                detail="For financial cyber-fraud loss in India, call 1930 promptly. Do not delay this while completing the app's questions.",
                destination="1930",
                urgency="urgent",
            ),
            GuidanceItem(
                title="File an online cybercrime complaint",
                detail="Submit a complaint through the National Cyber Crime Reporting Portal and retain the acknowledgement/reference number.",
                destination="National Cyber Crime Reporting Portal",
                url="https://cybercrime.gov.in/",
                urgency="urgent",
            ),
            GuidanceItem(
                title="Preserve evidence",
                detail="Keep transaction IDs, bank alerts, messages, call details and timestamps. Do not delete relevant evidence.",
                urgency="important",
            ),
        ])
        return analysis.incident_type, "urgent_response", "You reported financial loss. Contact your bank immediately, call 1930 promptly and file a cybercrime complaint. Do not wait for further analysis.", actions

    if analysis.credentials_shared_reported:
        actions.extend([
            GuidanceItem(
                title="Contact your bank immediately",
                detail="Use an independently verified official bank channel. Tell the bank that a banking credential or OTP was disclosed and ask it to secure the account, review recent activity and block or disable affected payment instruments or sessions where appropriate.",
                urgency="urgent",
            ),
            GuidanceItem(
                title="Secure affected accounts",
                detail="From a trusted device, change the affected password or PIN where applicable, sign out unknown sessions and revoke suspicious access. Never share another OTP or PIN with anyone.",
                urgency="urgent",
            ),
            GuidanceItem(
                title="Check for unauthorised transactions",
                detail="Review your bank statement and recent transactions. If any money has been debited, call 1930 promptly and file at https://cybercrime.gov.in/.",
                destination="National Cyber Crime Reporting Portal (if loss or cybercrime is confirmed/suspected)",
                url="https://cybercrime.gov.in/",
                urgency="important",
            ),
            GuidanceItem(
                title="Preserve evidence",
                detail="Keep messages, call logs, alerts and timestamps. Do not include the secret itself in your report to this app.",
                urgency="important",
            ),
            GuidanceItem(
                title="Report suspected cybercrime to I4C when appropriate",
                detail="If you believe your credential was obtained through a cybercrime or your account may have been misused, submit a complaint through the National Cyber Crime Reporting Portal. If money is debited, call 1930 promptly as well.",
                destination="National Cyber Crime Reporting Portal",
                url="https://cybercrime.gov.in/",
                urgency="important",
            ),
        ])
        return analysis.incident_type, "urgent_protective_action", "You reported sharing a sensitive credential. Contact the affected provider or bank through an independently verified official channel now, even if no debit is visible yet.", actions

    if analysis.risk_level in ("high", "critical"):
        actions.extend([
            GuidanceItem(
                title="Stop the suspicious access",
                detail="Do not continue interacting with the caller, link or app. If you installed remote-access software, disconnect the session and remove its access using trusted device-security guidance.",
                urgency="urgent",
            ),
            GuidanceItem(
                title="Secure affected accounts and device",
                detail="Use a trusted device to review account sessions, revoke unknown access and contact the relevant provider through independently verified official channels.",
                urgency="urgent",
            ),
        ])

    actions.extend([
        GuidanceItem(
            title="Do not transfer money to an unverified caller",
            detail="Do not return money to an account or UPI ID supplied by an unverified caller. Do not scan their QR code or approve a collect request.",
            urgency="important",
        ),
        GuidanceItem(
            title="Verify independently with your bank",
            detail="Check your own bank app or statement. If an unexpected credit is genuinely present, do not spend or move it; contact your bank through independently obtained official channels.",
            urgency="important",
        ),
        GuidanceItem(
            title="Report suspicious communication",
            detail="Chakshu on Sanchar Saathi accepts reports of suspected fraudulent communications. It is not a substitute for reporting actual financial loss.",
            destination="Chakshu — Sanchar Saathi",
            url="https://sancharsaathi.gov.in/sfc/",
            urgency="informational",
        ),
        GuidanceItem(
            title="Report a suspect identifier where applicable",
            detail="If a phone number or identifier was used in an attempted cybercrime, consider the I4C Report Suspect facility.",
            destination="I4C Report Suspect",
            url="https://cybercrime.gov.in/Webform/cyber_suspect.aspx",
            urgency="informational",
        ),
    ])
    status = "needs_clarification" if analysis.mode == "needs_clarification" else "prevention"
    summary = "The narration contains possible warning signs, but it does not establish that a crime occurred. Do not send money or share credentials based on the caller's instructions. Verify any claimed transaction independently."
    return analysis.incident_type, status, summary, actions
