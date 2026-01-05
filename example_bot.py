import asyncio
from simpx import BotProfile, SimpleXBot
from simpx.extension import ChatWrapper
from typing import List
import traceback

try:
  from openai import OpenAI
  aiclient = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="<API_KEY_HERE>",
  )
except ImportError:
  aiclient = None

CHAT_MODEL = "google/gemini-2.0-flash-lite-001"

# Example usage
if __name__ == "__main__":
    
    # Create a bot profile
    profile = BotProfile(
        display_name="ExampleBot",
        full_name="Example Bot",
        description="An example bot using SimpX-py framework",
        welcome_message="Hello {name}! I'm an example bot. Try /help to see what I can do.",
        auto_accept_message="This is the example bot!",
        command_prefix="!"
    )
    
    # Create the bot with the profile
    bot = SimpleXBot(profile)
    
    @bot.command(name="info", help="Shows bot information")
    async def info_command(chat_info, profile):
        """Command that shows information about the bot's profile."""
        await bot.send_message(
            chat_info,
            f"*Bot Information*\n"
            f"Name: {profile.display_name}\n"
            f"Description: {profile.description}\n"
            f"Address: {profile.address}"
        )
    
    @bot.command(name="echo", help="Echoes your message")
    async def echo_command(chat_info, args):
        await bot.send_message(chat_info, f"You said: {args}")
        
    @bot.command(name="square", help="Calculates the square of a number")
    async def square_command(chat_info, args):
        try:
            number = float(args.strip())
            result = number * number
            await bot.send_message(chat_info, f"{number} × {number} = {result}")
        except ValueError:
            await bot.send_message(chat_info, "Please provide a valid number to square.")
    
    @bot.command(name="add", pattern=r"add (?P<a>\d+) (?P<b>\d+)", help="Adds two numbers")
    async def add_command(chat_info, a, b):
        result = int(a) + int(b)
        await bot.send_message(chat_info, f"{a} + {b} = {result}")

    if aiclient is not None:
      @bot.command(name="msg", help="Ask an AI a question and get a live-streamed response")
      async def ask_command(chat_info, args):
          """
          Demonstrate live messaging with an AI streaming response from OpenRouter.
          
          Args:
              chat_info: Chat information dictionary.
              args: User's prompt.
          """
          # Create a ChatWrapper instance using the provided chat_info and the bot's client.
          chat = ChatWrapper(chat_info, bot.client)
          
          try:
              # Start a live message session with an initial text.
              initial_text = "Processing your request..."
              live_msg = await bot.send_message(chat, initial_text, live=True, ttl=60)
              current_response = ""
              
              
              # Create the chat completion request with streaming enabled.
              response = aiclient.chat.completions.create(
                  model=CHAT_MODEL,
                  messages=[
                      {
                          "role": "user",
                          "content": [
                              {
                                  "type": "text",
                                  "text": args
                              }
                          ]
                      }
                  ],
                  stream=True  # Enable streaming of the response.
              )
              
              # Process each streaming chunk.
              for chunk in response:
                  # Extract text content from the current chunk.
                  # Assumes chunk structure similar to OpenAI's streaming response.
                  chunk_text = chunk.choices[0].delta.content or ""
                  if chunk_text:
                      current_response += chunk_text
                      # Update the live message with the accumulated response.
                      await live_msg.update_live(f"{current_response}")
              
              # Finalize the live message.
              await live_msg.finish_live()
          
          except Exception as e:
              # In case of error, finalize the live message.
              traceback.print_exc()
              await live_msg.finish_live()

    # Start the bot
    asyncio.run(bot.start())

