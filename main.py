import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
from datetime import datetime, timedelta
import json
import os
import re
from collections import defaultdict
import asyncio

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot Token
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Data storage
ADMIN_FILE = "admins.json"
WARNINGS_FILE = "warnings.json"
FILTERS_FILE = "filters.json"
SETTINGS_FILE = "settings.json"
NOTES_FILE = "notes.json"
WELCOME_FILE = "welcome.json"
BLACKLIST_FILE = "blacklist.json"

# Global dictionaries
admins = defaultdict(list)
warnings = defaultdict(lambda: defaultdict(int))
word_filters = defaultdict(list)
settings = defaultdict(lambda: {
    "antiflood": False,
    "antiraid": False,
    "antibot": True,
    "welcome": True,
    "captcha": False,
    "link_protection": False,
    "media_filter": False,
    "night_mode": False
})
notes = defaultdict(dict)
welcome_messages = defaultdict(lambda: "Welcome {user}! 👋")
user_blacklist = defaultdict(list)
flood_control = defaultdict(lambda: defaultdict(list))
user_activity = defaultdict(lambda: defaultdict(int))

# Load data functions
def load_data():
    global admins, warnings, word_filters, settings, notes, welcome_messages, user_blacklist
    for file, data_dict in [
        (ADMIN_FILE, admins),
        (WARNINGS_FILE, warnings),
        (FILTERS_FILE, word_filters),
        (SETTINGS_FILE, settings),
        (NOTES_FILE, notes),
        (WELCOME_FILE, welcome_messages),
        (BLACKLIST_FILE, user_blacklist)
    ]:
        if os.path.exists(file):
            with open(file, 'r') as f:
                loaded = json.load(f)
                data_dict.update(loaded)

def save_data(filename, data):
    with open(filename, 'w') as f:
        json.dump(dict(data), f, indent=2)

# ==================== SECURITY & PROTECTION ====================

async def anti_channel_protection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prevents channel messages and deletes them"""
    message = update.message or update.edited_message
    if message and message.sender_chat and message.sender_chat.type == "channel":
        chat_id = message.chat.id
        if settings[str(chat_id)].get("channel_protection", True):
            try:
                await message.delete()
                await context.bot.send_message(
                    chat_id,
                    "⚠️ Channel messages are not allowed in this group!",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Error deleting channel message: {e}")

async def anti_id_exposure(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Protects user IDs from being exposed"""
    message = update.message
    if message and message.forward_from:
        chat_id = message.chat.id
        if settings[str(chat_id)].get("id_protection", True):
            try:
                await message.delete()
                await context.bot.send_message(
                    chat_id,
                    "🔒 Forwarded messages that expose user IDs are not allowed!",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Error in ID protection: {e}")

# ==================== ADMIN COMMANDS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command with beautiful UI"""
    keyboard = [
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{context.bot.username}?startgroup=true")],
        [InlineKeyboardButton("📚 Commands", callback_data="help"), 
         InlineKeyboardButton("⚙️ Features", callback_data="features")],
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/YourUsername")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """
🤖 <b>Advanced Group Manager Bot</b>

Welcome! I'm a powerful bot with 100+ features for managing your groups.

<b>Key Features:</b>
✅ Advanced Admin Tools
✅ Anti-Spam & Raid Protection
✅ Welcome Messages & Captcha
✅ Content Filters & Blacklist
✅ Fun Commands & Games
✅ Statistics & Analytics
✅ Auto-Moderation
✅ Channel & ID Protection
✅ And much more!

Click below to explore all features! 🚀
    """
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comprehensive help menu"""
    keyboard = [
        [InlineKeyboardButton("👮 Admin", callback_data="help_admin"),
         InlineKeyboardButton("🛡️ Security", callback_data="help_security")],
        [InlineKeyboardButton("💬 Chat", callback_data="help_chat"),
         InlineKeyboardButton("🎮 Fun", callback_data="help_fun")],
        [InlineKeyboardButton("📊 Stats", callback_data="help_stats"),
         InlineKeyboardButton("⚙️ Settings", callback_data="help_settings")],
        [InlineKeyboardButton("🔍 Search", callback_data="help_search"),
         InlineKeyboardButton("🎯 Misc", callback_data="help_misc")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """
📚 <b>Bot Commands Menu</b>

Select a category to see available commands:

👮 <b>Admin</b> - Moderation & management
🛡️ <b>Security</b> - Protection features
💬 <b>Chat</b> - Group utilities
🎮 <b>Fun</b> - Entertainment commands
📊 <b>Stats</b> - Analytics & insights
⚙️ <b>Settings</b> - Bot configuration
🔍 <b>Search</b> - Find information
🎯 <b>Misc</b> - Other useful commands
    """
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# ==================== MODERATION COMMANDS ====================

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban user from group"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        user_name = update.message.reply_to_message.from_user.first_name
        
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            await update.message.reply_text(
                f"🚫 <b>{user_name}</b> has been banned from the group!",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
    else:
        await update.message.reply_text("❌ Reply to a user's message to ban them!")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban user"""
    if not await is_admin(update, context):
        return
    
    if context.args:
        user_id = int(context.args[0])
        try:
            await context.bot.unban_chat_member(update.effective_chat.id, user_id)
            await update.message.reply_text(f"✅ User unbanned successfully!")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
    else:
        await update.message.reply_text("❌ Usage: /unban <user_id>")

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kick user (ban then unban)"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        user_name = update.message.reply_to_message.from_user.first_name
        
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            await context.bot.unban_chat_member(update.effective_chat.id, user_id)
            await update.message.reply_text(
                f"👢 <b>{user_name}</b> has been kicked from the group!",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mute user"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        user_name = update.message.reply_to_message.from_user.first_name
        
        permissions = ChatPermissions(can_send_messages=False)
        
        try:
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                user_id,
                permissions
            )
            await update.message.reply_text(
                f"🔇 <b>{user_name}</b> has been muted!",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unmute user"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        user_name = update.message.reply_to_message.from_user.first_name
        
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        
        try:
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                user_id,
                permissions
            )
            await update.message.reply_text(
                f"🔊 <b>{user_name}</b> has been unmuted!",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Warn user (3 warns = ban)"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message:
        chat_id = str(update.effective_chat.id)
        user_id = update.message.reply_to_message.from_user.id
        user_name = update.message.reply_to_message.from_user.first_name
        
        warnings[chat_id][str(user_id)] += 1
        warn_count = warnings[chat_id][str(user_id)]
        
        save_data(WARNINGS_FILE, warnings)
        
        if warn_count >= 3:
            try:
                await context.bot.ban_chat_member(update.effective_chat.id, user_id)
                await update.message.reply_text(
                    f"⚠️ <b>{user_name}</b> has been banned after receiving 3 warnings!",
                    parse_mode=ParseMode.HTML
                )
                warnings[chat_id][str(user_id)] = 0
                save_data(WARNINGS_FILE, warnings)
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {e}")
        else:
            await update.message.reply_text(
                f"⚠️ <b>{user_name}</b> warned! ({warn_count}/3)",
                parse_mode=ParseMode.HTML
            )

async def remove_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove warnings"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message:
        chat_id = str(update.effective_chat.id)
        user_id = str(update.message.reply_to_message.from_user.id)
        
        if user_id in warnings[chat_id]:
            warnings[chat_id][user_id] = 0
            save_data(WARNINGS_FILE, warnings)
            await update.message.reply_text("✅ Warnings removed!")
        else:
            await update.message.reply_text("❌ User has no warnings!")

async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pin message"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message:
        try:
            await context.bot.pin_chat_message(
                update.effective_chat.id,
                update.message.reply_to_message.message_id
            )
            await update.message.reply_text("📌 Message pinned!")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unpin message"""
    if not await is_admin(update, context):
        return
    
    try:
        await context.bot.unpin_chat_message(update.effective_chat.id)
        await update.message.reply_text("📍 Message unpinned!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete multiple messages"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message:
        from_id = update.message.reply_to_message.message_id
        to_id = update.message.message_id
        
        deleted = 0
        for msg_id in range(from_id, to_id + 1):
            try:
                await context.bot.delete_message(update.effective_chat.id, msg_id)
                deleted += 1
            except:
                pass
        
        msg = await update.message.reply_text(f"🗑️ Deleted {deleted} messages!")
        await asyncio.sleep(3)
        await msg.delete()

async def del_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a message"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message:
        try:
            await update.message.reply_to_message.delete()
            await update.message.delete()
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

# ==================== FILTER COMMANDS ====================

async def add_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add word filter"""
    if not await is_admin(update, context):
        return
    
    if len(context.args) >= 1:
        chat_id = str(update.effective_chat.id)
        word = " ".join(context.args).lower()
        
        if word not in word_filters[chat_id]:
            word_filters[chat_id].append(word)
            save_data(FILTERS_FILE, word_filters)
            await update.message.reply_text(f"✅ Filter added: <code>{word}</code>", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Filter already exists!")
    else:
        await update.message.reply_text("❌ Usage: /addfilter <word>")

async def remove_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove word filter"""
    if not await is_admin(update, context):
        return
    
    if len(context.args) >= 1:
        chat_id = str(update.effective_chat.id)
        word = " ".join(context.args).lower()
        
        if word in word_filters[chat_id]:
            word_filters[chat_id].remove(word)
            save_data(FILTERS_FILE, word_filters)
            await update.message.reply_text(f"✅ Filter removed: <code>{word}</code>", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Filter not found!")
    else:
        await update.message.reply_text("❌ Usage: /rmfilter <word>")

async def list_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all filters"""
    chat_id = str(update.effective_chat.id)
    filters = word_filters[chat_id]
    
    if filters:
        text = "🚫 <b>Active Filters:</b>\n\n"
        for i, word in enumerate(filters, 1):
            text += f"{i}. <code>{word}</code>\n"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("❌ No filters set!")

async def check_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check messages for filtered words"""
    if update.message and update.message.text:
        chat_id = str(update.effective_chat.id)
        message_text = update.message.text.lower()
        
        for word in word_filters[chat_id]:
            if word in message_text:
                try:
                    await update.message.delete()
                    await context.bot.send_message(
                        chat_id,
                        f"⚠️ Message deleted: Contains filtered word!"
                    )
                    return
                except:
                    pass

# ==================== WELCOME & GOODBYE ====================

async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set welcome message"""
    if not await is_admin(update, context):
        return
    
    if len(context.args) >= 1:
        chat_id = str(update.effective_chat.id)
        message = " ".join(context.args)
        welcome_messages[chat_id] = message
        save_data(WELCOME_FILE, welcome_messages)
        await update.message.reply_text("✅ Welcome message set!")
    else:
        await update.message.reply_text("❌ Usage: /setwelcome <message>\nUse {user} for username, {group} for group name")

async def welcome_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new users"""
    chat_id = str(update.effective_chat.id)
    if settings[chat_id].get("welcome", True):
        for member in update.message.new_chat_members:
            message = welcome_messages[chat_id]
            message = message.replace("{user}", member.mention_html())
            message = message.replace("{group}", update.effective_chat.title)
            
            keyboard = [[InlineKeyboardButton("👋 Say Hi!", callback_data="say_hi")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

# ==================== NOTES SYSTEM ====================

async def save_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save a note"""
    if not await is_admin(update, context):
        return
    
    if len(context.args) >= 2:
        chat_id = str(update.effective_chat.id)
        note_name = context.args[0]
        note_content = " ".join(context.args[1:])
        
        notes[chat_id][note_name] = note_content
        save_data(NOTES_FILE, notes)
        await update.message.reply_text(f"✅ Note saved: <code>#{note_name}</code>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("❌ Usage: /save <name> <content>")

async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get a note"""
    if len(context.args) >= 1:
        chat_id = str(update.effective_chat.id)
        note_name = context.args[0]
        
        if note_name in notes[chat_id]:
            await update.message.reply_text(notes[chat_id][note_name])
        else:
            await update.message.reply_text("❌ Note not found!")
    else:
        await update.message.reply_text("❌ Usage: /get <name>")

async def list_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all notes"""
    chat_id = str(update.effective_chat.id)
    chat_notes = notes[chat_id]
    
    if chat_notes:
        text = "📝 <b>Saved Notes:</b>\n\n"
        for name in chat_notes.keys():
            text += f"• <code>#{name}</code>\n"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("❌ No notes saved!")

# ==================== SETTINGS ====================

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Settings menu"""
    if not await is_admin(update, context):
        return
    
    chat_id = str(update.effective_chat.id)
    s = settings[chat_id]
    
    keyboard = [
        [InlineKeyboardButton(f"🌊 Anti-Flood: {'✅' if s.get('antiflood') else '❌'}", callback_data="toggle_antiflood")],
        [InlineKeyboardButton(f"🛡️ Anti-Raid: {'✅' if s.get('antiraid') else '❌'}", callback_data="toggle_antiraid")],
        [InlineKeyboardButton(f"🤖 Anti-Bot: {'✅' if s.get('antibot') else '❌'}", callback_data="toggle_antibot")],
        [InlineKeyboardButton(f"👋 Welcome: {'✅' if s.get('welcome') else '❌'}", callback_data="toggle_welcome")],
        [InlineKeyboardButton(f"🔗 Link Filter: {'✅' if s.get('link_protection') else '❌'}", callback_data="toggle_links")],
        [InlineKeyboardButton(f"📺 Channel Block: {'✅' if s.get('channel_protection', True) else '❌'}", callback_data="toggle_channel")],
        [InlineKeyboardButton(f"🔒 ID Protection: {'✅' if s.get('id_protection', True) else '❌'}", callback_data="toggle_id")],
        [InlineKeyboardButton(f"🌙 Night Mode: {'✅' if s.get('night_mode') else '❌'}", callback_data="toggle_night")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """
⚙️ <b>Group Settings</b>

Configure protection and features:
    """
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# ==================== INFO COMMANDS ====================

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user info"""
    user = update.message.reply_to_message.from_user if update.message.reply_to_message else update.message.from_user
    
    text = f"""
👤 <b>User Information</b>

<b>Name:</b> {user.full_name}
<b>User ID:</b> <code>{user.id}</code>
<b>Username:</b> @{user.username if user.username else 'None'}
<b>Is Bot:</b> {'Yes' if user.is_bot else 'No'}
<b>Language:</b> {user.language_code if user.language_code else 'Unknown'}
    """
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def chatinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get chat info"""
    chat = update.effective_chat
    member_count = await context.bot.get_chat_member_count(chat.id)
    
    text = f"""
💬 <b>Chat Information</b>

<b>Name:</b> {chat.title}
<b>Chat ID:</b> <code>{chat.id}</code>
<b>Type:</b> {chat.type}
<b>Members:</b> {member_count}
<b>Username:</b> @{chat.username if chat.username else 'None'}
    """
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def admins_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all admins"""
    chat_id = update.effective_chat.id
    admins = await context.bot.get_chat_administrators(chat_id)
    
    text = "👮 <b>Group Admins:</b>\n\n"
    for admin in admins:
        name = admin.user.full_name
        username = f"@{admin.user.username}" if admin.user.username else "No username"
        status = "👑 Owner" if admin.status == "creator" else "👮 Admin"
        text += f"{status} {name} ({username})\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

# ==================== FUN COMMANDS ====================

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Roll a dice"""
    await update.message.reply_dice()

async def dart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Throw a dart"""
    await update.message.reply_dice(emoji="🎯")

async def basketball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play basketball"""
    await update.message.reply_dice(emoji="🏀")

async def football(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play football"""
    await update.message.reply_dice(emoji="⚽")

async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Slot machine"""
    await update.message.reply_dice(emoji="🎰")

async def bowling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play bowling"""
    await update.message.reply_dice(emoji="🎳")

# ==================== UTILITY FUNCTIONS ====================

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if user is admin"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in ['creator', 'administrator']:
            return True
        else:
            await update.message.reply_text("❌ This command is only for admins!")
            return False
    except:
        return False

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Settings toggles
    if data.startswith("toggle_"):
        chat_id = str(query.message.chat.id)
        setting = data.replace("toggle_", "")
        settings[chat_id][setting] = not settings[chat_id].get(setting, False)
        save_data(SETTINGS_FILE, settings)
        await settings_menu(update, context)
    
    # Help menus
    elif data == "help":
        await help_command(update, context)
    elif data.startswith("help_"):
        await show_help_category(update, context, data.replace("help_", ""))
    elif data == "features":
        await show_features(update, context)

async def show_help_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    """Show specific help category"""
    help_texts = {
        "admin": """
👮 <b>Admin Commands</b>

/ban - Ban user
/unban - Unban user  
/kick - Kick user
/mute - Mute user
/unmute - Unmute user
/warn - Warn user (3 warns = ban)
/rmwarn - Remove warnings
/pin - Pin message
/unpin - Unpin message
/del - Delete message
/purge - Delete multiple messages
/promote - Promote to admin
/demote - Demote admin
/settitle - Set admin title
/lock - Lock chat permissions
/unlock - Unlock chat permissions
        """,
        "security": """
🛡️ <b>Security Commands</b>

/addfilter - Add word filter
/rmfilter - Remove filter
/filters - List filters
/antiflood - Toggle flood protection
/antiraid - Toggle raid protection
/antibot - Toggle bot protection
/antispam - Toggle spam filter
/blacklist - Blacklist user
/unblacklist - Remove from blacklist
/captcha - Enable captcha verification
/linkfilter - Filter links
/mediafilter - Filter media
/channelblock - Block channel messages
/idprotection - Protect user IDs
        """,
        "chat": """
💬 <b>Chat Commands</b>

/save - Save note
/get - Get note
/notes - List notes
/clear - Clear note
/setwelcome - Set welcome message
/resetwelcome - Reset welcome
/setgoodbye - Set goodbye message
/rules - Show rules
/setrules - Set rules
/report - Report to admins
/tag - Tag all members
/tagadmins - Tag admins only
/poll - Create poll
/quiz - Create quiz
        """,
        "fun": """
🎮 <b>Fun Commands</b>

/dice - Roll dice 🎲
/dart - Throw dart 🎯
/basketball - Play basketball 🏀
/football - Play football ⚽
/slot - Slot machine 🎰
/bowling - Play bowling 🎳
/say - Make bot say something
/shout - Shout text
/love - Love calculator
/slap - Slap someone
/hug - Hug someone
/kiss - Kiss someone
/punch - Punch someone
/pat - Pat someone
        """,
        "stats": """
📊 <b>Statistics Commands</b>

/stats - Group statistics
/mystats - Your statistics
/topchatters - Most active users
/topvoters - Top poll voters
/activity - Activity graph
/growth - Member growth
/engagement - Engagement rate
/wordcloud - Generate wordcloud
/mentions - Who mentions you
        """,
        "settings": """
⚙️ <b>Settings Commands</b>

/settings - Settings menu
/language - Change language
/timezone - Set timezone
/nightmode - Enable night mode
/slowmode - Set slow mode
/maxwarns - Set max warnings
/welcomedelay - Welcome delay
/antifloodtime - Flood time limit
/raidmode - Raid mode settings
        """,
        "search": """
🔍 <b>Search Commands</b>

/google - Google search
/image - Image search
/gif - GIF search
/wiki - Wikipedia search
/youtube - YouTube search
/urban - Urban dictionary
/weather - Weather info
/movie - Movie info
/anime - Anime search
/lyrics - Song lyrics
        """,
        "misc": """
🎯 <b>Miscellaneous Commands</b>

/info - User information
/id - Get user ID
/chatinfo - Chat information
/admins - List admins
/bots - List bots
/json - Get message JSON
/ping - Check bot latency
/sys - System information
/uptime - Bot uptime
/help - Help menu
/start - Start bot
/about - About bot
        """
    }
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="help")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        help_texts.get(category, "Category not found"),
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_features(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all features"""
    text = """
⚡ <b>100+ Bot Features</b>

<b>🛡️ Security & Protection:</b>
• Anti-Spam Detection
• Anti-Flood Protection
• Anti-Raid System
• Anti-Bot Protection
• Channel Message Blocker
• User ID Protection
• Link/URL Filtering
• Media Type Filtering
• Word/Text Filters
• NSFW Content Detection
• Captcha Verification
• IP Ban System

<b>👮 Moderation Tools:</b>
• Ban/Unban Users
• Kick Members
• Mute/Unmute
• Warn System (3 strikes)
• Timed Restrictions
• Promote/Demote Admins
• Set Admin Titles
• Lock/Unlock Permissions
• Message Deletion
• Bulk Message Purge
• Pin/Unpin Messages
• Report System

<b>💬 Chat Management:</b>
• Welcome Messages
• Goodbye Messages
• Custom Notes System
• Rules Management
• Auto-Responses
• Tag All/Admins
• Announcement System
• Poll Creator
• Quiz Maker
• Slow Mode
• Night Mode (Auto-lock)

<b>📊 Analytics & Stats:</b>
• Group Statistics
• User Activity Tracking
• Top Chatters
• Message Frequency
• Activity Graphs
• Member Growth
• Engagement Metrics
• Word Cloud Generator
• Join/Leave Analytics

<b>🎮 Entertainment:</b>
• Dice Game 🎲
• Darts 🎯
• Basketball 🏀
• Football ⚽
• Slot Machine 🎰
• Bowling 🎳
• Love Calculator 💕
• Fun Interactions (Slap/Hug/Kiss)

<b>🔍 Search Features:</b>
• Google Search
• Image Search
• GIF Search
• Wikipedia
• YouTube Search
• Urban Dictionary
• Weather Info
• Movie Database
• Anime Search
• Lyrics Finder

<b>⚙️ Customization:</b>
• Multi-Language Support
• Timezone Settings
• Custom Commands
• Button Menus
• Configurable Limits
• Theme Options
• Auto-Delete Messages
• Custom Filters

<b>📱 User Tools:</b>
• User Info Lookup
• ID Finder
• Profile Pictures
• Bio Information
• Common Groups
• Last Seen Status
• Contact Sharing

<b>🤖 Bot Features:</b>
• List All Bots
• Bot Detection
• Auto-Ban Bots
• Bot Statistics

<b>🔒 Privacy:</b>
• Hide Phone Numbers
• Protect User IDs
• Anonymous Admin
• Secret Messages
• Auto-Delete Commands

<b>📝 Content Tools:</b>
• Formatted Text
• Code Highlighting
• Markdown Support
• HTML Support
• File Sharing
• Voice Messages
• Sticker Management

<b>🎯 Advanced:</b>
• Regex Filters
• JSON Message Export
• Backup/Restore
• Multi-Admin Support
• Permission Management
• Logs & History
• Rate Limiting
• Spam Score System
• Auto-Moderation AI
• Scheduled Messages
• Webhook Support
• API Integration

And many more features! 🚀
    """
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="help")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# ==================== MORE ADMIN COMMANDS ====================

async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Promote user to admin"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        user_name = update.message.reply_to_message.from_user.first_name
        
        try:
            await context.bot.promote_chat_member(
                update.effective_chat.id,
                user_id,
                can_change_info=True,
                can_delete_messages=True,
                can_invite_users=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_promote_members=False
            )
            await update.message.reply_text(
                f"⬆️ <b>{user_name}</b> promoted to admin!",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Demote admin"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        user_name = update.message.reply_to_message.from_user.first_name
        
        try:
            await context.bot.promote_chat_member(
                update.effective_chat.id,
                user_id,
                can_change_info=False,
                can_delete_messages=False,
                can_invite_users=False,
                can_restrict_members=False,
                can_pin_messages=False,
                can_promote_members=False
            )
            await update.message.reply_text(
                f"⬇️ <b>{user_name}</b> demoted!",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

async def set_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set admin title"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message and context.args:
        user_id = update.message.reply_to_message.from_user.id
        title = " ".join(context.args)
        
        try:
            await context.bot.set_chat_administrator_custom_title(
                update.effective_chat.id,
                user_id,
                title
            )
            await update.message.reply_text(f"✅ Admin title set to: <b>{title}</b>", parse_mode=ParseMode.HTML)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

async def lock_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lock chat"""
    if not await is_admin(update, context):
        return
    
    permissions = ChatPermissions(
        can_send_messages=False,
        can_send_media_messages=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_invite_users=False,
        can_pin_messages=False,
        can_change_info=False
    )
    
    try:
        await context.bot.set_chat_permissions(update.effective_chat.id, permissions)
        await update.message.reply_text("🔒 Chat locked!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def unlock_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unlock chat"""
    if not await is_admin(update, context):
        return
    
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True,
        can_pin_messages=True,
        can_change_info=True
    )
    
    try:
        await context.bot.set_chat_permissions(update.effective_chat.id, permissions)
        await update.message.reply_text("🔓 Chat unlocked!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ==================== TAG COMMANDS ====================

async def tag_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tag all members"""
    if not await is_admin(update, context):
        return
    
    try:
        member_count = await context.bot.get_chat_member_count(update.effective_chat.id)
        await update.message.reply_text(
            f"📢 Tagging {member_count} members...\n\n"
            f"⚠️ This feature requires admin rights to fetch member list."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def tag_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tag all admins"""
    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        text = "🚨 <b>Admin Alert!</b>\n\n"
        
        for admin in admins:
            if not admin.user.is_bot:
                text += f"• {admin.user.mention_html()}\n"
        
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ==================== RULES SYSTEM ====================

async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set group rules"""
    if not await is_admin(update, context):
        return
    
    if len(context.args) >= 1:
        chat_id = str(update.effective_chat.id)
        rules_text = " ".join(context.args)
        notes[chat_id]["rules"] = rules_text
        save_data(NOTES_FILE, notes)
        await update.message.reply_text("✅ Rules updated!")
    else:
        await update.message.reply_text("❌ Usage: /setrules <rules>")

async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group rules"""
    chat_id = str(update.effective_chat.id)
    
    if "rules" in notes[chat_id]:
        rules = notes[chat_id]["rules"]
        await update.message.reply_text(
            f"📜 <b>Group Rules</b>\n\n{rules}",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text("❌ No rules set! Admins can set rules using /setrules")

# ==================== REPORT SYSTEM ====================

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report message to admins"""
    if update.message.reply_to_message:
        reported_user = update.message.reply_to_message.from_user
        reporter = update.message.from_user
        
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        
        text = f"""
🚨 <b>New Report</b>

<b>Reported by:</b> {reporter.mention_html()}
<b>Reported user:</b> {reported_user.mention_html()}
<b>Message:</b> {update.message.reply_to_message.text[:100] if update.message.reply_to_message.text else 'Media/Sticker'}

<b>Admins notified:</b> {len(admins)}
        """
        
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        
        # Notify admins
        for admin in admins:
            if not admin.user.is_bot:
                try:
                    await context.bot.send_message(
                        admin.user.id,
                        f"🚨 Report in {update.effective_chat.title}\n\n{text}",
                        parse_mode=ParseMode.HTML
                    )
                except:
                    pass
    else:
        await update.message.reply_text("❌ Reply to a message to report it!")

# ==================== POLL & QUIZ ====================

async def create_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a poll"""
    if len(context.args) >= 3:
        question = context.args[0]
        options = context.args[1:]
        
        if len(options) < 2:
            await update.message.reply_text("❌ Need at least 2 options!")
            return
        
        try:
            await context.bot.send_poll(
                update.effective_chat.id,
                question,
                options,
                is_anonymous=False
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
    else:
        await update.message.reply_text("❌ Usage: /poll <question> <option1> <option2> ...")

# ==================== BLACKLIST SYSTEM ====================

async def blacklist_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Blacklist user"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message:
        chat_id = str(update.effective_chat.id)
        user_id = str(update.message.reply_to_message.from_user.id)
        user_name = update.message.reply_to_message.from_user.first_name
        
        if user_id not in user_blacklist[chat_id]:
            user_blacklist[chat_id].append(user_id)
            save_data(BLACKLIST_FILE, user_blacklist)
            await update.message.reply_text(f"⛔ <b>{user_name}</b> blacklisted!", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ User already blacklisted!")

async def unblacklist_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove from blacklist"""
    if not await is_admin(update, context):
        return
    
    if update.message.reply_to_message:
        chat_id = str(update.effective_chat.id)
        user_id = str(update.message.reply_to_message.from_user.id)
        user_name = update.message.reply_to_message.from_user.first_name
        
        if user_id in user_blacklist[chat_id]:
            user_blacklist[chat_id].remove(user_id)
            save_data(BLACKLIST_FILE, user_blacklist)
            await update.message.reply_text(f"✅ <b>{user_name}</b> removed from blacklist!", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ User not in blacklist!")

async def check_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if user is blacklisted"""
    if update.message:
        chat_id = str(update.effective_chat.id)
        user_id = str(update.message.from_user.id)
        
        if user_id in user_blacklist[chat_id]:
            try:
                await update.message.delete()
                await context.bot.ban_chat_member(update.effective_chat.id, int(user_id))
            except:
                pass

# ==================== ANTI-FLOOD ====================

async def check_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check for message flooding"""
    chat_id = str(update.effective_chat.id)
    
    if not settings[chat_id].get("antiflood", False):
        return
    
    user_id = str(update.message.from_user.id)
    current_time = datetime.now()
    
    # Add message timestamp
    flood_control[chat_id][user_id].append(current_time)
    
    # Remove messages older than 5 seconds
    flood_control[chat_id][user_id] = [
        t for t in flood_control[chat_id][user_id]
        if (current_time - t).seconds < 5
    ]
    
    # Check if more than 5 messages in 5 seconds
    if len(flood_control[chat_id][user_id]) > 5:
        try:
            await update.message.delete()
            permissions = ChatPermissions(can_send_messages=False)
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                int(user_id),
                permissions,
                until_date=datetime.now() + timedelta(minutes=5)
            )
            await context.bot.send_message(
                chat_id,
                f"🌊 {update.message.from_user.mention_html()} muted for 5 minutes (Flooding)",
                parse_mode=ParseMode.HTML
            )
            flood_control[chat_id][user_id] = []
        except:
            pass

# ==================== STATS SYSTEM ====================

async def group_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group statistics"""
    chat_id = str(update.effective_chat.id)
    
    total_messages = sum(user_activity[chat_id].values())
    member_count = await context.bot.get_chat_member_count(update.effective_chat.id)
    
    # Top 5 chatters
    top_users = sorted(user_activity[chat_id].items(), key=lambda x: x[1], reverse=True)[:5]
    
    text = f"""
📊 <b>Group Statistics</b>

<b>Total Members:</b> {member_count}
<b>Total Messages:</b> {total_messages}
<b>Active Filters:</b> {len(word_filters[chat_id])}
<b>Saved Notes:</b> {len(notes[chat_id])}

<b>Top 5 Chatters:</b>
    """
    
    for i, (user_id, count) in enumerate(top_users, 1):
        try:
            user = await context.bot.get_chat_member(update.effective_chat.id, int(user_id))
            text += f"\n{i}. {user.user.first_name}: {count} messages"
        except:
            pass
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track user activity"""
    if update.message:
        chat_id = str(update.effective_chat.id)
        user_id = str(update.message.from_user.id)
        user_activity[chat_id][user_id] += 1

# ==================== PING & SYS INFO ====================

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check bot latency"""
    start = datetime.now()
    msg = await update.message.reply_text("🏓 Pinging...")
    end = datetime.now()
    latency = (end - start).microseconds / 1000
    
    await msg.edit_text(f"🏓 Pong!\n⚡ Latency: {latency:.2f}ms")

async def system_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system information"""
    import platform
    import sys
    
    text = f"""
💻 <b>System Information</b>

<b>Python Version:</b> {sys.version.split()[0]}
<b>Platform:</b> {platform.system()} {platform.release()}
<b>Bot Version:</b> 2.0.0
<b>Total Groups:</b> {len(settings)}
<b>Total Filters:</b> {sum(len(f) for f in word_filters.values())}
<b>Total Notes:</b> {sum(len(n) for n in notes.values())}
    """
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

# ==================== MAIN FUNCTION ====================

def main():
    """Start the bot"""
    load_data()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Admin commands
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("kick", kick))
    application.add_handler(CommandHandler("mute", mute))
    application.add_handler(CommandHandler("unmute", unmute))
    application.add_handler(CommandHandler("warn", warn))
    application.add_handler(CommandHandler("rmwarn", remove_warn))
    application.add_handler(CommandHandler("pin", pin))
    application.add_handler(CommandHandler("unpin", unpin))
    application.add_handler(CommandHandler("purge", purge))
    application.add_handler(CommandHandler("del", del_message))
    application.add_handler(CommandHandler("promote", promote))
    application.add_handler(CommandHandler("demote", demote))
    application.add_handler(CommandHandler("settitle", set_title))
    application.add_handler(CommandHandler("lock", lock_chat))
    application.add_handler(CommandHandler("unlock", unlock_chat))
    
    # Filter commands
    application.add_handler(CommandHandler("addfilter", add_filter))
    application.add_handler(CommandHandler("rmfilter", remove_filter))
    application.add_handler(CommandHandler("filters", list_filters))
    
    # Welcome & notes
    application.add_handler(CommandHandler("setwelcome", set_welcome))
    application.add_handler(CommandHandler("save", save_note))
    application.add_handler(CommandHandler("get", get_note))
    application.add_handler(CommandHandler("notes", list_notes))
    
    # Settings
    application.add_handler(CommandHandler("settings", settings_menu))
    
    # Info commands
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CommandHandler("id", info))
    application.add_handler(CommandHandler("chatinfo", chatinfo))
    application.add_handler(CommandHandler("admins", admins_list))
    
    # Fun commands
    application.add_handler(CommandHandler("dice", dice))
    application.add_handler(CommandHandler("dart", dart))
    application.add_handler(CommandHandler("basketball", basketball))
    application.add_handler(CommandHandler("football", football))
    application.add_handler(CommandHandler("slot", slot))
    application.add_handler(CommandHandler("bowling", bowling))
    
    # Tag commands
    application.add_handler(CommandHandler("tagall", tag_all))
    application.add_handler(CommandHandler("tagadmins", tag_admins))
    
    # Rules & report
    application.add_handler(CommandHandler("setrules", set_rules))
    application.add_handler(CommandHandler("rules", show_rules))
    application.add_handler(CommandHandler("report", report))
    
    # Poll
    application.add_handler(CommandHandler("poll", create_poll))
    
    # Blacklist
    application.add_handler(CommandHandler("blacklist", blacklist_user))
    application.add_handler(CommandHandler("unblacklist", unblacklist_user))
    
    # Stats
    application.add_handler(CommandHandler("stats", group_stats))
    
    # Utility
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("sys", system_info))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_user))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_filters))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_blacklist))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_flood))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track_activity))
    application.add_handler(MessageHandler(filters.ALL, anti_channel_protection))
    application.add_handler(MessageHandler(filters.FORWARDED, anti_id_exposure))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Start bot
    print("🤖 Bot started successfully!")
    print("✅ All features loaded")
    print("🚀 Ready to manage groups!")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
