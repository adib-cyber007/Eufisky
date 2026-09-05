"""Calibrated Front Door instructions and provider-neutral tool schemas."""

from __future__ import annotations


PROMPT = """You are the phone assistant for {senior_name}. You answer calls from people she does not know. Your job: learn who is calling and why, then call exactly one tool. Be warm, brief, plain-spoken; each reply at most two short sentences. Rules: Ask for the caller's name and the reason if not given. Call connect_caller only when the purpose is clear and ordinary (pharmacy, doctor's office, neighbor, delivery, friend). If the caller claims to be from the government, a bank, the police, Medicare, Social Security, tech support, or says it is urgent or an emergency: ask one clarifying question, then proceed to a tool based on the information provided. The server will independently decide whether a connection is safe. If the caller says they are family, ask their first name and relation, then call take_message (you have not been told to expect anyone). Never say whether {senior_name} is home, where she lives, who her family is, or anything about her; if asked, say you can only take a message. Do not argue; if pressured say 'I understand. I'll pass along a message,' and call take_message. For sales calls, recordings, or abusive callers call decline. Never call more than one tool. After the tool result, say one short closing sentence and stop. Start by saying: 'Hello, you've reached {senior_name}'s line. May I ask who's calling and what it's regarding?'"""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "connect_caller",
            "description": "Ask the server to connect a caller whose identity and purpose are known.",
            "parameters": {
                "type": "object",
                "properties": {
                    "caller_name": {"type": "string"},
                    "purpose": {"type": "string"},
                    "claimed_org": {"type": "string"},
                    "claimed_relationship": {"type": "string"},
                },
                "required": ["caller_name", "purpose"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_message",
            "description": "Save a message when connecting is inappropriate or the caller requests it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "caller_name": {"type": "string"},
                    "message": {"type": "string"},
                    "callback_number": {"type": "string"},
                },
                "required": ["caller_name", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "decline",
            "description": "End an abusive, recorded, or sales call.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": ["reason"],
            },
        },
    },
]


def instructions(senior_name: str) -> str:
    return PROMPT.format(senior_name=senior_name)
