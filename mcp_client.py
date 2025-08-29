from praisonaiagents import Agent, MCP
from dotenv import load_dotenv
import os
import litellm
from openai import OpenAI

load_dotenv()

# Configure LLM - simplified Gemini configuration
llm_config = {
    "model": "gemini/gemini-2.5-flash",  # or "gemini-flash" for faster responses
    "temperature": 0.7,
    "max_tokens": 2048
}

# Properly escaped Windows path
tool_path = r"python C:\Users\shani\OneDrive\Desktop\Mcp_making\whatsapp-mcp\whatsapp-mcp-server\main.py"

whatsapp = Agent(
    instructions="You are a WhatsApp assistant. Your task is to help manage and analyze WhatsApp messages. "
                "When listing messages, provide clear, organized information including timestamps and sender names.",
    llm=llm_config,
    tools=MCP(tool_path)
)

# Start with clearer instructions
whatsapp.start(
    "Send a message to Safwan Ali stating that   'this is ai generated message.Stay tuned'. "
    "If using tools, ensure the input is a valid dictionary format."
    "use all necessary tools you want"
)