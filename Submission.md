## Startup-

It requires installing these libraries - openai, google-genai python-dotenv

```bash
pip install python-dotenv google-genai openai
```

## Features

- **Triple-Model Selection and Verifier**: Before start, you can choose which model you want to use for the agent from the three available options. Also has a Verifier model that fact checks the answers given by this agent when asked to. Implemented in `Initialize_Chat` function.

- **Can Choose Memory Limit**: You can choose how many messages the bot can remembers in the conversation before summarizing it. Implemented in `Initialize_Chat` function.

- **Nature Customization**: You can choose the type of nature the agent will have from three different pre-built styles.  Implemented in `Initialize_Chat` function.

- **Typewritter Effect**: All messages don't print suddenly, they have the typewritter effect that LLMs generally have so that wait time decreases and interface looks good. This is done with the help of streaming responses from AI and using the `slow_print` function that I made.

- **Prompt Checking**: Using Gemini to smartly check if user wants to get an answer from agent or if he wants to verify previous assistant's response. Implemented in `check_critic` method of `ChatBot` class.

- **Summary Generation**: Auto summarizes message after memory fills or if the user uses `/summarize` command. Prints summary if it gets generated via command(not if it is auto-generated or if the user is exiting.). Saving tokens by only generating summary if any conversation exists after last summary generation. Remembers last conversation briefly even after summary generation in case user wants to use Verifier.

- **Error Handling**: Defaults for every customizable setting in `Initialize_Chat` function in case of errors or wrong values, try-except blocks for ai-response in case if AI faces high-demand to try again and prevent errors. Verifier checks before running if assistant response exists, preventing index out of range crashes.

- **Clean Exit**: If the user types exit to exit or in case of KeyboardInterrupt or any other errors while talking with ai agent, the agent first generates a chat summary and then generates an exit message for the user based on the summary. Implimented in `exit` method of `ChatBot` class.

## Example run of agent.py-

```bash
=== Welcome to the Dual-Agent AI Interface ===

Let's get your session set up.

Which primary AI engine would you like to use today?
  [1] Owl Alpha
  [2] GLM 4.5 Air
  [3] GPT OSS 120b

Enter your choice (1-3): 3
=> Model GPT OSS 120b selected.

How many messages should the AI remember before compressing its memory?
(Choose between 5 and 15. Higher limits keep more context but may delay responses.)

Enter memory limit: 2
=> Limit too low. Increased to 5.

Finally, what kind of personality would you like your AI to have?
  [1] Strictly Professional
  [2] Friendly & Casual
  [3] A Balanced Blend

Enter personality choice (1-3): 4
=> Unknown input. Defaulting to Blended nature.
-------------------------------------------------------
System Commands:
 • Type '/summarize' to manually compress the chat history.
 • Ask 'Is this correct?' or something similar to trigger the Gemini Fact-Checker.
 • Type 'exit' to gracefully end the session.
-------------------------------------------------------
Initializing your AI...

Agent: Hello! I’m ChatGPT, here to help with any questions or tasks you have. How can I assist you today?
User: Hii, What is today's date and day?
Agent: Today’s date is **June 5, 2026**, and it falls on a **Saturday**. How can I help you further?
User: Is it correct?
Verifier: The previous AI's answer contains an error.

While an AI does not have a "today's date" in the human sense, if it provides a specific date, the associated day of the week must be accurate.

For the date **June 5, 2026**, the correct day of the week is **Friday**, not Saturday.
User: /summarize
Summarizing messages till now. Please wait...
Messages summarized.
Summarized History: *   **AI Persona:** Helpful, friendly, welcoming, professional, reliable, clear, efficient, focused, polite.
*   **AI Communication Protocol:** Warmly introduce self, politely ask how to support, maintain focus and pacing.
*   **User Query:** What is today's date and day? (Followed by verification of provided date/day).
*   **Previous AI Statement:** June 5, 2026, is a Saturday.
*   **Established Fact/Correction:** June 5, 2026, is a Friday.
*   **AI Capability/Constraint:** AI does not have a "today's date" in the human sense.
*   **AI Output Requirement:** If a date is provided, the associated day of the week must be accurate.
*   **Ongoing Task:** Confirming accurate date and day information.
User: exit
Exiting...
Agent: Thank you for your time, and I hope the rest of your day goes wonderfully. I'm always here whenever you need assistance, so feel free to return anytime.
```