"""
Optional LLM narration layer.

The reconciliation decision itself is made entirely by the deterministic
rule engine in reconciler.py — that logic must work with zero external
dependencies, because it's the part that has to be defensible and
reproducible. This module's only job is to turn the structured decision
trail into a short, readable paragraph for a human reviewer, using
Google's Gemini API (free tier: https://aistudio.google.com/apikey).

If GEMINI_API_KEY isn't set, or the `google-genai` package isn't
installed, or the API call fails for any reason, this falls back to a
template-based summary built from the same structured data. Nothing
about the reconciliation result depends on the LLM being available —
it only affects how nicely the explanation reads.
"""

import os


def _template_summary(reconciled_asset) -> str:
    lines = [f"Reconciled asset {reconciled_asset.asset_id}:"]
    for name, f in reconciled_asset.fields.items():
        flag = " [CONTRADICTION RESOLVED]" if f.contradiction_flagged else ""
        lines.append(f"- {name}: {f.value!r} (source: {f.chosen_source}, "
                      f"confidence: {f.confidence.value}){flag}")
    return "\n".join(lines)


def narrate(reconciled_asset) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return _template_summary(reconciled_asset) + \
            "\n\n(Set GEMINI_API_KEY to get an LLM-written narrative summary here instead.)"

    try:
        from google import genai
    except ImportError:
        return _template_summary(reconciled_asset) + \
            "\n\n(Install the SDK to enable LLM narration: pip install google-genai)"

    try:
        client = genai.Client(api_key=api_key)

        field_summaries = []
        for name, f in reconciled_asset.fields.items():
            field_summaries.append(
                f"- {name}: value={f.value!r}, chosen_source={f.chosen_source}, "
                f"confidence={f.confidence.value}, contradiction={f.contradiction_flagged}, "
                f"reasoning={f.reasoning}"
            )
        prompt = (
            "You are summarizing an asset-state reconciliation agent's decisions for a "
            "human auditor. Below is the structured decision record for one asset. Write "
            "a tight, plain-English summary (5-8 sentences max) of what the agent decided "
            "and why, calling out any contradictions it resolved and how. Do not invent "
            "any facts not present below. Be direct, not promotional.\n\n"
            f"Asset: {reconciled_asset.asset_id}\n" + "\n".join(field_summaries)
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        return _template_summary(reconciled_asset) + f"\n\n(LLM narration failed: {e})"
