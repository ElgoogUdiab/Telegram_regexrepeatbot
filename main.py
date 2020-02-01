from telegram.ext import Updater
import json
from telegram.ext import CommandHandler, MessageHandler, ConversationHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
import requests
import re
import rstr
from copy import copy

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    with open("token") as f:
        token = f.readline().strip()
except:
    print("No token! Create file named \"token\" under the same directory with main.py!")
    exit(1)
try:
    with open("pattern.json") as f:
        patterns = json.load(f)
except:
    patterns = {}

updater = Updater(token=token, use_context=True)
dispatcher = updater.dispatcher

url = "https://{lang}.wikipedia.org/wiki/Special:Random"

def update_pattern(chat_id, patt=None):
    global patterns
    if not str(chat_id) in patterns:
        patterns.update({str(chat_id): {"patterns": {}}})
    if patt != None:
        name = patt.pop("name")
        patterns[str(chat_id)]["patterns"].update({name: patt})
    with open("pattern.json", "w") as f:
        json.dump(patterns, f)

def start(update, context):
    # context.bot.send_message(chat_id=update.effective_chat.id, text=str(update.effective_chat.id))
    update_pattern(str(update.effective_chat.id), None)
start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

PATTERN, RESPONSE_REGEX, RESPONSE_PATTERN = range(3)
def add_pattern(update, context):
    if len(context.args) != 1:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /add <Rule name>")
        return ConversationHandler.END
    name = context.args[0]
    print(0)
    print(patterns)
    if name in patterns[str(update.effective_chat.id)]["patterns"]:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Rule with same name exists!")
        return ConversationHandler.END
    data = context.user_data
    data.update({"name": name})
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! Setting rule {name}.\nNow give me the pattern.\nNote: You can cancel at any time by typing /cancel")
    return PATTERN
def define_pattern(update, context):
    pattern = update.message.text
    try:
        re.compile(pattern)
    except re.error:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Seems not a valid regex. Please try again.")
        return PATTERN
    data = context.user_data
    data.update({"pattern": pattern})
    keyboard = [
        [InlineKeyboardButton("Yes", callback_data="Yes"),
         InlineKeyboardButton("No", callback_data="No")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! The pattern is {pattern}.\nWould you please tell me whether the response is a regex or not?", reply_markup=reply_markup)
    return RESPONSE_REGEX
def define_whether_regex_false(update, context):
    data = context.user_data
    data.update({"is_regex": False})
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! The reply text is NOT a regex.\nNow give the response.")
    return RESPONSE_PATTERN
def define_whether_regex_true(update, context):
    data = context.user_data
    data.update({"is_regex": True})
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! The reply text is a regex.\nNow give the response.")
    return RESPONSE_PATTERN
def define_response(update, context):
    data = context.user_data
    response = update.message.text
    if data["is_regex"]:
        pass
    data.update({"response": response})
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! The reply text is {response}.\nThis rule should be functioning now.")
    update_pattern(update.effective_chat.id, copy(data))
    data.clear()
    print(patterns)
    return ConversationHandler.END

def cancel(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"OK! Canceled")
    data = context.user_data
    data.clear()
    return ConversationHandler.END

add_pattern_handler = ConversationHandler(
    entry_points=[CommandHandler('add', add_pattern, pass_args=True)],
    states = {
        PATTERN: [MessageHandler(Filters.text, define_pattern)],
        RESPONSE_REGEX: [
            CallbackQueryHandler(define_whether_regex_true, pattern=r"^Yes$"),
            CallbackQueryHandler(define_whether_regex_false, pattern=r"^No$")
        ],
        RESPONSE_PATTERN: [MessageHandler(Filters.text, define_response)]
    },
    fallbacks = [CommandHandler('cancel', cancel, pass_args=True)]
)
dispatcher.add_handler(add_pattern_handler)

def del_pattern(update, context):
    if len(context.args)!=1:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Usage: /del <Rule name>")
        return
    name = context.args[0]
    if not name in patterns[str(update.effective_chat.id)]["patterns"]:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Rule not found!")
        return
    patterns[str(update.effective_chat.id)]["patterns"].pop(name)
    update_pattern(str(update.effective_chat.id))
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"Rule deleted.")
del_pattern_handler = CommandHandler('del', del_pattern, pass_args=True)
dispatcher.add_handler(del_pattern_handler)


def show_patterns(update, context):
    try:
        pattern = patterns[str(update.effective_chat.id)]["patterns"]
    except:
        pattern = {}
    print(pattern)
    if not pattern:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"No rule here.")
    else:
        out_str = "Here are the rules:\n"
        out_str += "\n".join([f"{name}: {patt['pattern']} -> {patt['response']}" for name, patt in pattern.items()])
        context.bot.send_message(chat_id=update.effective_chat.id, text=out_str)
show_pattern_handler = CommandHandler('show', show_patterns)
dispatcher.add_handler(show_pattern_handler)

"""
def processing():
    pass
echo_handler = MessageHandler(Filter.text, processing)
dispatcher.add_handler(echo_handler)
"""

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)
dispatcher.add_error_handler(error)

print(json.dumps(patterns, indent=4, ensure_ascii=False))

updater.start_polling()
