import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters, JobQueue
from telegram.request import HTTPXRequest
from telegram.error import BadRequest
from telegram import ReplyKeyboardMarkup, Update
from pymongo import MongoClient
import certifi
import logging
from pymongo.errors import PyMongoError
import requests
import time as tm
import re
import random
import asyncio

# Load environment variables
load_dotenv()

# Console logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

# Database configuration using environment variables (MongoDB)
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://davekindea1993_db_user:lcdtkjjNzkWwNcdS@cluster0.bfg4n8z.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
MONGO_DB = os.getenv("MONGO_DB", "datingbot")

# Telegram bot configuration
TOKEN = os.getenv("TELEGRAM_TOKEN", "8195099645:AAHX9KAgjEpouTyWZKN9cNp2Y7Q8F3bsafI")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@AACoTbot")

# Initialize MongoDB client (collections wired later)
_mongo_client = MongoClient(MONGO_URI, tlsCAFile=certifi.where()) if ("mongodb.net" in MONGO_URI or MONGO_URI.startswith("mongodb+srv")) else MongoClient(MONGO_URI)
_mongo_db = _mongo_client[MONGO_DB]
_users = _mongo_db["Users"]
_likes = _mongo_db["Likes"]
_reports = _mongo_db["Reports"]
_banned = _mongo_db["banned"]

# Keep existing exception handlers working
class mysql:
    class connector:
        Error = PyMongoError

# Database health check
def is_db_connected():
    try:
        _mongo_db.command("ping")
        logger.info("MongoDB ping successful")
        return True
    except Exception as e:
        logger.error("MongoDB ping failed: %s", e)
        return False

# SQL-like cursor/connection shims over MongoDB
class _FakeCursor:
    def __init__(self):
        self._last = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=()):
        q = " ".join(query.split())
        # banned
        if q.startswith("SELECT * FROM banned WHERE PersonID = %s"):
            person_id = params[0]
            doc = _banned.find_one({"PersonID": person_id})
            self._last = [tuple(doc.values())] if doc else []
            return

        # user completeness (active/inactive)
        if q.startswith("SELECT COUNT(*) FROM Users WHERE PersonID = %s") and "IsActive = 1" in q:
            person_id = params[0]
            count = _users.count_documents({
                "PersonID": person_id,
                "UserName": {"$ne": None},
                "Age": {"$ne": None},
                "Gender": {"$ne": None},
                "Looking": {"$ne": None},
                "City": {"$ne": None},
                "Bio": {"$ne": None},
                "Photo": {"$ne": None},
                "IsActive": 1,
            })
            self._last = [(count,)]
            return
        if q.startswith("SELECT COUNT(*) FROM Users WHERE PersonID = %s") and "IsActive = 0" in q:
            person_id = params[0]
            count = _users.count_documents({
                "PersonID": person_id,
                "UserName": {"$ne": None},
                "Age": {"$ne": None},
                "Gender": {"$ne": None},
                "Looking": {"$ne": None},
                "City": {"$ne": None},
                "Bio": {"$ne": None},
                "Photo": {"$ne": None},
                "IsActive": 0,
            })
            self._last = [(count,)]
            return

        # user selects
        if q.startswith("SELECT UserName, Age, City, Bio, Photo, Premium FROM Users WHERE PersonID = %s"):
            person_id = params[0]
            d = _users.find_one({"PersonID": person_id}) or {}
            self._last = [(d.get("UserName"), d.get("Age"), d.get("City"), d.get("Bio"), d.get("Photo"), d.get("Premium", 0))]
            return
        if q.startswith("SELECT UserName, Age, Bio, Photo, Premium FROM Users WHERE PersonID = %s"):
            person_id = params[0]
            d = _users.find_one({"PersonID": person_id}) or {}
            self._last = [(d.get("UserName"), d.get("Age"), d.get("Bio"), d.get("Photo"), d.get("Premium", 0))]
            return
        if q.startswith("SELECT PersonID FROM Users WHERE PersonID = %s"):
            person_id = params[0]
            d = _users.find_one({"PersonID": person_id})
            self._last = [(d.get("PersonID"),)] if d else []
            return
        if q.startswith("SELECT Bio FROM Users WHERE PersonID = %s"):
            person_id = params[0]
            d = _users.find_one({"PersonID": person_id}) or {}
            self._last = [(d.get("Bio"),)]
            return
        if q.startswith("SELECT Photo FROM Users WHERE PersonID = %s"):
            person_id = params[0]
            d = _users.find_one({"PersonID": person_id}) or {}
            self._last = [(d.get("Photo"),)]
            return

        # user inserts/updates
        if q.startswith("INSERT INTO Users (PersonID, UserName, IsActive) VALUES"):
            person_id, user_name = params
            _users.update_one({"PersonID": person_id}, {"$setOnInsert": {"PersonID": person_id}, "$set": {"UserName": user_name, "IsActive": 1}}, upsert=True)
            self._last = []
            return
        if q.startswith("UPDATE Users SET UserName = %s, IsActive = 1 WHERE PersonID = %s"):
            user_name, person_id = params
            _users.update_one({"PersonID": person_id}, {"$set": {"UserName": user_name, "IsActive": 1}})
            self._last = []
            return
        if q.startswith("UPDATE Users SET Age = %s WHERE PersonID = %s"):
            age, person_id = params
            _users.update_one({"PersonID": person_id}, {"$set": {"Age": age}})
            self._last = []
            return
        if q.startswith("UPDATE Users SET Gender = %s WHERE PersonID = %s"):
            gender, person_id = params
            _users.update_one({"PersonID": person_id}, {"$set": {"Gender": gender}})
            self._last = []
            return
        if q.startswith("UPDATE Users SET Looking = %s WHERE PersonID = %s"):
            looking, person_id = params
            _users.update_one({"PersonID": person_id}, {"$set": {"Looking": looking}})
            self._last = []
            return
        if q.startswith("UPDATE Users SET City = %s WHERE PersonID = %s"):
            city, person_id = params
            _users.update_one({"PersonID": person_id}, {"$set": {"City": city}})
            self._last = []
            return
        if q.startswith("UPDATE Users SET Bio = %s WHERE PersonID = %s"):
            bio, person_id = params
            _users.update_one({"PersonID": person_id}, {"$set": {"Bio": bio}})
            self._last = []
            return
        if q.startswith("UPDATE Users SET Photo = %s WHERE PersonID = %s"):
            photo, person_id = params
            _users.update_one({"PersonID": person_id}, {"$set": {"Photo": photo}})
            self._last = []
            return
        if q.startswith("UPDATE Users SET IsActive = 1 WHERE PersonID = %s"):
            person_id = params[0]
            _users.update_one({"PersonID": person_id}, {"$set": {"IsActive": 1}})
            self._last = []
            return
        if q.startswith("UPDATE Users SET IsActive = 0 WHERE PersonID = %s"):
            person_id = params[0]
            _users.update_one({"PersonID": person_id}, {"$set": {"IsActive": 0}})
            self._last = []
            return

        if q.startswith("SELECT DailyViewCount, Premium FROM Users WHERE PersonID = %s"):
            person_id = params[0]
            d = _users.find_one({"PersonID": person_id}) or {}
            self._last = [(d.get("DailyViewCount", 0), d.get("Premium", 0))]
            return
        if q.startswith("SELECT Looking, Gender FROM Users WHERE PersonID = %s"):
            person_id = params[0]
            d = _users.find_one({"PersonID": person_id}) or {}
            self._last = [(d.get("Looking"), d.get("Gender"))]
            return
        if q.startswith("SELECT Age FROM Users WHERE PersonID = %s") and "Bio IS NOT NULL" in q:
            person_id = params[0]
            d = _users.find_one({"PersonID": person_id, "Bio": {"$ne": None}, "Photo": {"$ne": None}}) or {}
            self._last = [(d.get("Age"))]
            return
        if q.startswith("UPDATE Users SET DailyViewCount = DailyViewCount - 1 WHERE PersonID = %s"):
            person_id = params[0]
            _users.update_one({"PersonID": person_id}, {"$inc": {"DailyViewCount": -1}})
            self._last = []
            return

        # Likes
        if q.startswith("SELECT LikeUserID FROM Likes WHERE LikedUserID = %s"):
            liked_id = params[0]
            docs = list(_likes.find({"LikedUserID": liked_id}, {"_id": 0, "LikeUserID": 1}))
            self._last = [(doc.get("LikeUserID"),) for doc in docs]
            return
        if q.startswith("SELECT PersonID, UserName, Age, Bio, Photo FROM Users JOIN Likes ON PersonID = LikeUserID WHERE LikedUserID = %s"):
            liked_id = params[0]
            pipeline = [
                {"$match": {"LikedUserID": liked_id}},
                {"$lookup": {"from": "Users", "localField": "LikeUserID", "foreignField": "PersonID", "as": "user"}},
                {"$unwind": "$user"},
                {"$project": {"_id": 0, "PersonID": "$user.PersonID", "UserName": "$user.UserName", "Age": "$user.Age", "Bio": "$user.Bio", "Photo": "$user.Photo"}}
            ]
            rows = [(d["PersonID"], d["UserName"], d["Age"], d["Bio"], d["Photo"]) for d in _likes.aggregate(pipeline)]
            self._last = rows
            return
        if q.startswith("SELECT MesToPerson FROM Likes WHERE LikeUserID = %s AND LikedUserID = %s"):
            like_user, liked_user = params
            d = _likes.find_one({"LikeUserID": like_user, "LikedUserID": liked_user}) or {}
            self._last = [(d.get("MesToPerson", None),)]
            return
        if q.startswith("SELECT * FROM Likes WHERE LikeUserID = %s AND LikedUserID = %s"):
            like_user, liked_user = params
            d = _likes.find_one({"LikeUserID": like_user, "LikedUserID": liked_user})
            self._last = [tuple(d.values())] if d else []
            return
        if q.startswith("INSERT INTO Likes (LikeUserID, LikedUserID) VALUES"):
            like_user, liked_user = params
            _likes.update_one({"LikeUserID": like_user, "LikedUserID": liked_user}, {"$setOnInsert": {"LikeUserID": like_user, "LikedUserID": liked_user}}, upsert=True)
            self._last = []
            return
        if q.startswith("INSERT INTO Likes (LikeUserID, LikedUserID, MesToPerson) VALUES"):
            like_user, liked_user, msg = params
            _likes.update_one({"LikeUserID": like_user, "LikedUserID": liked_user}, {"$set": {"MesToPerson": msg}}, upsert=True)
            self._last = []
            return
        if q.startswith("DELETE FROM Likes WHERE LikeUserID = %s AND LikedUserID = %s"):
            like_user, liked_user = params
            _likes.delete_one({"LikeUserID": like_user, "LikedUserID": liked_user})
            self._last = []
            return
        if q.startswith("DELETE FROM Likes WHERE LikedUserID = %s AND LikeUserID = %s"):
            liked_user, like_user = params
            _likes.delete_one({"LikeUserID": like_user, "LikedUserID": liked_user})
            self._last = []
            return

        # Reports
        if q.startswith("SELECT COUNT(*) FROM Reports WHERE UserID = %s"):
            uid = params[0]
            count = _reports.count_documents({"UserID": uid})
            self._last = [(count,)]
            return
        if q.startswith("UPDATE Reports SET AdultREP = AdultREP + 1 WHERE UserID = %s"):
            uid = params[0]
            _reports.update_one({"UserID": uid}, {"$inc": {"AdultREP": 1}}, upsert=True)
            self._last = []
            return
        if q.startswith("UPDATE Reports SET DrugREP = DrugREP + 1 WHERE UserID = %s"):
            uid = params[0]
            _reports.update_one({"UserID": uid}, {"$inc": {"DrugREP": 1}}, upsert=True)
            self._last = []
            return
        if q.startswith("UPDATE Reports SET SaleREP = SaleREP + 1 WHERE UserID = %s"):
            uid = params[0]
            _reports.update_one({"UserID": uid}, {"$inc": {"SaleREP": 1}}, upsert=True)
            self._last = []
            return
        if q.startswith("UPDATE Reports SET OtherREP = OtherREP + 1 WHERE UserID = %s"):
            uid = params[0]
            _reports.update_one({"UserID": uid}, {"$inc": {"OtherREP": 1}}, upsert=True)
            self._last = []
            return
        if q.startswith("INSERT INTO Reports (UserID, AdultREP) VALUES"):
            uid = params[0]
            _reports.update_one({"UserID": uid}, {"$set": {"AdultREP": 1}}, upsert=True)
            self._last = []
            return
        if q.startswith("INSERT INTO Reports (UserID, DrugREP) VALUES"):
            uid = params[0]
            _reports.update_one({"UserID": uid}, {"$set": {"DrugREP": 1}}, upsert=True)
            self._last = []
            return
        if q.startswith("INSERT INTO Reports (UserID, SaleREP) VALUES"):
            uid = params[0]
            _reports.update_one({"UserID": uid}, {"$set": {"SaleREP": 1}}, upsert=True)
            self._last = []
            return
        if q.startswith("INSERT INTO Reports (UserID, OtherREP) VALUES"):
            uid = params[0]
            _reports.update_one({"UserID": uid}, {"$set": {"OtherREP": 1}}, upsert=True)
            self._last = []
            return

        # Matching pool count and selection
        if q.startswith("SELECT COUNT(*) FROM Users WHERE Gender = %s AND Looking = %s"):
            match_gender, user_looking, like_user_id, age_min, age_max, not_id = params
            liked_ids = set(d.get("LikedUserID") for d in _likes.find({"LikeUserID": like_user_id}, {"_id": 0, "LikedUserID": 1}))
            count = _users.count_documents({
                "Gender": match_gender,
                "Looking": user_looking,
                "IsActive": 1,
                "PersonID": {"$ne": not_id, "$nin": list(liked_ids)},
                "Age": {"$gte": age_min, "$lte": age_max},
                "Bio": {"$ne": None},
                "Photo": {"$ne": None}
            })
            self._last = [(count,)]
            return
        if q.startswith("SELECT PersonID, UserName, Age, Bio, Photo FROM Users WHERE Gender = %s AND Looking = %s") and "LIMIT 1 OFFSET %s" in q:
            match_gender, user_looking, like_user_id, age_min, age_max, offset = params
            liked_ids = set(d.get("LikedUserID") for d in _likes.find({"LikeUserID": like_user_id}, {"_id": 0, "LikedUserID": 1}))
            cur = _users.find({
                "Gender": match_gender,
                "Looking": user_looking,
                "IsActive": 1,
                "PersonID": {"$nin": list(liked_ids)},
                "Age": {"$gte": age_min, "$lte": age_max},
                "Bio": {"$ne": None},
                "Photo": {"$ne": None}
            }, {"_id": 0, "PersonID": 1, "UserName": 1, "Age": 1, "Bio": 1, "Photo": 1}).skip(offset).limit(1)
            docs = list(cur)
            if docs:
                d = docs[0]
                self._last = [(d.get("PersonID"), d.get("UserName"), d.get("Age"), d.get("Bio"), d.get("Photo"))]
            else:
                self._last = []
            return

        # default no-op
        self._last = []

    def fetchone(self):
        return self._last[0] if self._last else None

    def fetchall(self):
        return self._last or []

class _FakeConnection:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def cursor(self):
        return _FakeCursor()
    def commit(self):
        return None

class _FakePool:
    def get_connection(self):
        return _FakeConnection()

connection_pool = _FakePool()

# Conversation states
NAME, CHECK_USER_STATE, AGE, GENDER, LOOKING, CITY, BIO, CHANGEBIO, PHOTO, SAVEPHOTO, SAVE_MESSAGE, SHOW_PROFILE, MENU_EXE, WAIT_MENU_EXE, MATCHING, DEACTIVE, SHOW_WHO_LIKES, NONEACTIVE, REPORT_USER, BANNED, PREMIUM = range(21)

# Keyboard markups
gender_choice = ["Male", "Female"]
looking_choice = ["Boys", "Girls"]
region_choice = ["European side", "Istanbul side"]
leave_text_choice = ["Pass"]
leave_photo_choice = ["Leave current photo"]
yes_text = ["Yes"]
go_back_text = ["Go back"]
menu_choice = [["1", "2", "3", "4"]]
wait_menu_choice = [["1", "2", "3"]]
like_choice = [["❤️", "💌", "👎", "💤"]]
like_or_not_choice = [["❤️", "👎"]]
report_user_choice = [["1🔞", "2💊", "3💰", "4🦨", "9"]]
show_n_not_show_choice = [["1", "2"]]
show_who_likes_choice = ["Show.", "Not searching anymore."]
pay_choice = ["1 Month", "6 Months", "1 Year", "Go back"]
show_profiles = ["View profiles."]

# Create ReplyKeyboardMarkup objects
menu_markup = ReplyKeyboardMarkup(menu_choice, resize_keyboard=True, one_time_keyboard=True)
report_markup = ReplyKeyboardMarkup(report_user_choice, resize_keyboard=True, one_time_keyboard=True)
like_markup = ReplyKeyboardMarkup(like_choice, resize_keyboard=True, one_time_keyboard=True)
like_or_not_markup = ReplyKeyboardMarkup(like_or_not_choice, resize_keyboard=True, one_time_keyboard=True)
show_n_not_show_markup = ReplyKeyboardMarkup(show_n_not_show_choice, resize_keyboard=True, one_time_keyboard=True)
wait_menu_markup = ReplyKeyboardMarkup(wait_menu_choice, resize_keyboard=True, one_time_keyboard=True)

# Spam control variables
spams = {}
msgs = 7  # Messages in
max = 2   # Seconds
ban = 5   # Seconds

# Store user IDs
daily_user_id = {}
user_last_len = {}

def is_spam(user_id):
    """Check if user is spamming based on message rate."""
    try:
        usr = spams[user_id]
        usr["messages"] += 1
    except KeyError:
        spams[user_id] = {"next_time": int(tm.time()) + max, "messages": 1, "banned": 0}
        usr = spams[user_id]
    
    if usr["banned"] >= int(tm.time()):
        return True
    if usr["next_time"] >= int(tm.time()):
        if usr["messages"] >= msgs:
            spams[user_id]["banned"] = tm.time() + ban
            return True
    else:
        spams[user_id]["messages"] = 1
        spams[user_id]["next_time"] = int(tm.time()) + max
    return False

async def check_user_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check user state and direct to appropriate conversation state."""
    user_id = update.effective_user.id
    context.user_data['user_id'] = user_id
    daily_user_id[user_id] = user_id

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED

                cursor.execute(
                    "SELECT COUNT(*) FROM Users WHERE PersonID = %s AND UserName IS NOT NULL AND Age IS NOT NULL AND Gender IS NOT NULL AND Looking IS NOT NULL AND City IS NOT NULL AND Bio IS NOT NULL AND Photo IS NOT NULL AND IsActive = 1",
                    (user_id,)
                )
                user_exists = cursor.fetchone()[0] > 0

                cursor.execute(
                    "SELECT COUNT(*) FROM Users WHERE PersonID = %s AND UserName IS NOT NULL AND Age IS NOT NULL AND Gender IS NOT NULL AND Looking IS NOT NULL AND City IS NOT NULL AND Bio IS NOT NULL AND Photo IS NOT NULL AND IsActive = 0",
                    (user_id,)
                )
                user_exists_is_not_active = cursor.fetchone()[0] > 0

        if user_exists:
            with connection_pool.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT UserName, Age, City, Bio, Photo, Premium FROM Users WHERE PersonID = %s", (user_id,))
                    user_name, user_age, user_city, user_bio, user_photo, user_premium = cursor.fetchone()
            
            message_text = f"{user_name}, {user_age}, {user_city}, {user_bio or 'None'} {'| Premium ❤️‍🔥' if user_premium > 0 else ''}"
            await update.message.reply_text("Your profile:")
            await update.message.reply_photo(user_photo or 'None', caption=message_text)
            await update.message.reply_text(
                "1. Edit My Profile.\n2. Change My Profile Picture.\n3. Edit My Bio.\n4. Start Viewing Profiles.",
                reply_markup=menu_markup
            )
            return MENU_EXE
        elif user_exists_is_not_active:
            last_mes = context.user_data.get(user_id, update.message.text)
            if last_mes == "View profiles.":
                with connection_pool.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("UPDATE Users SET IsActive = 1 WHERE PersonID = %s", (user_id,))
                        conn.commit()
                        cursor.execute("SELECT UserName, Age, City, Bio, Photo, Premium FROM Users WHERE PersonID = %s", (user_id,))
                        user_name, user_age, user_city, user_bio, user_photo, user_premium = cursor.fetchone()
                
                message_text = f"{user_name}, {user_age}, {user_city}, {user_bio or 'None'} {'| Premium ❤️‍🔥' if user_premium > 0 else ''}"
                await update.message.reply_text("Your profile:")
                await update.message.reply_photo(user_photo or 'None', caption=message_text)
                await update.message.reply_text(
                    "1. Edit My Profile.\n2. Change My Profile Picture.\n3. Edit My Bio.\n4. Start Viewing Profiles.",
                    reply_markup=menu_markup
                )
                return MENU_EXE
            else:
                await update.message.reply_text(
                    "Hope you met someone with my help!\nAlways happy to chat. If bored, text me - I'll find someone special for you.\n1. View profiles",
                    reply_markup=ReplyKeyboardMarkup([show_profiles], resize_keyboard=True, one_time_keyboard=True)
                )
                return NONEACTIVE
        else:
            await update.message.reply_text(f"Hello! Welcome to {BOT_USERNAME}! Before we start, can you tell me your name?")
            return AGE
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again later.")
        return CHECK_USER_STATE

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = update.effective_user.id
    context.user_data['user_id'] = user_id
    daily_user_id[user_id] = user_id
    # Inform user if database connection is unavailable
    if not is_db_connected():
        await update.message.reply_text("Warning: database connection is unavailable right now. Some features may not work.")
    await update.message.reply_text(f"Hello! Welcome to {BOT_USERNAME}! Before we start, can you tell me your name?")
    return AGE

async def db_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report database connectivity status."""
    ok = is_db_connected()
    status = "connected" if ok else "not connected"
    logger.info("/db status requested -> %s", status)
    await update.message.reply_text(f"Database is {status}.")

async def on_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Suppress noisy transient network errors; log others
    err = context.error
    if err and err.__class__.__name__ in {"NetworkError"}:
        logger.warning("Transient network error: %s", err)
        return
    logger.exception("Unhandled error while processing update: %s", update, exc_info=err)

async def set_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's name and prompt for age."""
    user_id = context.user_data.get('user_id') or (update.effective_user.id if update and update.effective_user else None)
    if not user_id:
        # Unable to determine chat/user id, bail gracefully
        return AGE
    user_name = update.message.text

    if re.search(r'\d|\W|\s', user_name):
        await update.message.reply_text("Please enter a valid name!")
        return AGE

    context.user_data['user_name'] = user_name
    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                cursor.execute("SELECT PersonID FROM Users WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    cursor.execute("UPDATE Users SET UserName = %s, IsActive = 1 WHERE PersonID = %s", (user_name, user_id))
                else:
                    cursor.execute("INSERT INTO Users (PersonID, UserName, IsActive) VALUES (%s, %s, 1)", (user_id, user_name))
                conn.commit()
        
        await update.message.reply_text(f"Hello, {user_name}! Before we start, let's create your profile. 😋")
        await update.message.reply_text(f"{user_name}, how old are you?")
        return GENDER
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return AGE

async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's age and prompt for gender."""
    user_id = context.user_data.get('user_id')
    user_age = update.message.text

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
        
        try:
            user_age = int(user_age)
            if user_age < 18:
                await update.message.reply_text("If you are under 18 years of age you cannot be in this bot!!!\nPlease enter a valid age!")
                return GENDER
            if user_age > 99:
                await update.message.reply_text("Please enter a valid age!")
                return GENDER
            
            with connection_pool.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE Users SET Age = %s WHERE PersonID = %s", (user_age, user_id))
                    conn.commit()
            
            await update.message.reply_text("Specify your gender", reply_markup=ReplyKeyboardMarkup([gender_choice], resize_keyboard=True, one_time_keyboard=True))
            return LOOKING
        except ValueError:
            await update.message.reply_text("Please enter a valid age!")
            return GENDER
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return GENDER

async def set_looking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's gender and prompt for looking preference."""
    user_gender = update.message.text
    user_id = context.user_data.get('user_id')

    if user_gender not in gender_choice:
        await update.message.reply_text("Please select a valid gender!")
        return LOOKING

    context.user_data['user_gender'] = user_gender
    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                cursor.execute("UPDATE Users SET Gender = %s WHERE PersonID = %s", (user_gender, user_id))
                conn.commit()
        
        await update.message.reply_text("Who are you looking for?", reply_markup=ReplyKeyboardMarkup([looking_choice], resize_keyboard=True, one_time_keyboard=True))
        return CITY
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return LOOKING

async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's looking preference and prompt for city."""
    user_looking = update.message.text
    user_id = context.user_data.get('user_id')

    if user_looking not in looking_choice:
        await update.message.reply_text("Please select a valid option!")
        return CITY

    context.user_data['user_looking'] = user_looking
    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                cursor.execute("UPDATE Users SET Looking = %s WHERE PersonID = %s", (user_looking, user_id))
                conn.commit()
        
        await update.message.reply_text("Which city are you in? Please type your city name.")
        return BIO
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return CITY

async def set_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's city and prompt for bio."""
    user_city = update.message.text
    user_id = context.user_data.get('user_id')

    if not user_city or len(user_city.strip()) == 0:
        await update.message.reply_text("Please enter a valid city name!")
        return BIO

    context.user_data['user_city'] = user_city
    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                cursor.execute("UPDATE Users SET City = %s WHERE PersonID = %s", (user_city, user_id))
                conn.commit()
        
        await update.message.reply_text(
            "Tell more about yourself. Who are you looking for? What do you want to do? I'll find the best matches.",
            reply_markup=ReplyKeyboardMarkup([leave_text_choice], resize_keyboard=True, one_time_keyboard=True)
        )
        return PHOTO
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return BIO

async def set_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's bio and prompt for photo."""
    user_id = context.user_data.get('user_id')
    last_mes = update.message.text

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                
                if last_mes == "Pass":
                    cursor.execute("SELECT Bio FROM Users WHERE PersonID = %s", (user_id,))
                    result = cursor.fetchone()
                    if not result or not result[0]:
                        cursor.execute("UPDATE Users SET Bio = %s WHERE PersonID = %s", (".", user_id))
                        conn.commit()
                else:
                    user_bio = last_mes
                    context.user_data['user_bio'] = user_bio
                    cursor.execute("UPDATE Users SET Bio = %s WHERE PersonID = %s", (user_bio, user_id))
                    conn.commit()
        
        await update.message.reply_text(
            "Send your photo👍 for other users to see",
            reply_markup=ReplyKeyboardMarkup([leave_photo_choice], resize_keyboard=True, one_time_keyboard=True)
        )
        return SAVEPHOTO
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return PHOTO

async def save_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save user's photo and show profile."""
    user_id = context.user_data.get('user_id')
    last_mes = update.message.text

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                
                cursor.execute("SELECT Photo FROM Users WHERE PersonID = %s", (user_id,))
                photo_control = cursor.fetchone()

                if last_mes == "Leave current photo":
                    if photo_control and photo_control[0]:
                        await update.message.reply_text(
                            "Your profile is ready. Are you ready to continue?",
                            reply_markup=ReplyKeyboardMarkup([yes_text], resize_keyboard=True, one_time_keyboard=True)
                        )
                        return SHOW_PROFILE
                    else:
                        await update.message.reply_text("You do not have a saved photo, please send me a photo.")
                        return SAVEPHOTO
                
                if update.message.photo:
                    user_photo = update.message.photo[-1]
                    file = await context.bot.get_file(user_photo.file_id)
                    max_file_size_mb = 100
                    if file.file_size > max_file_size_mb * 1024 * 1024:
                        await update.message.reply_text(f"Invalid file size! File size should be less than {max_file_size_mb} MB.")
                        return SAVEPHOTO
                    
                    file_url = file.file_path
                    photo_url = f"root_folder/user_photos/{user_id}/{user_id}.png"
                    os.makedirs(os.path.dirname(photo_url), exist_ok=True)
                    
                    response = requests.get(file_url, timeout=10)
                    response.raise_for_status()
                    with open(photo_url, 'wb') as file:
                        file.write(response.content)
                    
                    cursor.execute("UPDATE Users SET Photo = %s WHERE PersonID = %s", (photo_url, user_id))
                    conn.commit()
                    
                    await update.message.reply_text(
                        "Your profile is ready. Are you ready to continue?",
                        reply_markup=ReplyKeyboardMarkup([yes_text], resize_keyboard=True, one_time_keyboard=True)
                    )
                    return SHOW_PROFILE
                else:
                    await update.message.reply_text("You have submitted an invalid file!")
                    return SAVEPHOTO
    except (mysql.connector.Error, requests.RequestException) as e:
        await context.bot.send_message(user_id, "Error processing your request. Please try again.")
        return SAVEPHOTO

async def change_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change user's bio and show profile."""
    user_id = context.user_data.get('user_id')
    last_mes = update.message.text

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                
                if last_mes == "Pass":
                    pass
                else:
                    user_bio = last_mes
                    context.user_data['user_bio'] = user_bio
                    cursor.execute("UPDATE Users SET Bio = %s WHERE PersonID = %s", (user_bio, user_id))
                    conn.commit()
        
        await update.message.reply_text(
            "Your profile is ready. Are you ready to continue?",
            reply_markup=ReplyKeyboardMarkup([yes_text], resize_keyboard=True, one_time_keyboard=True)
        )
        return SHOW_PROFILE
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return CHANGEBIO

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's profile and menu options."""
    user_id = context.user_data.get('user_id')
    last_mes = update.message.text

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                
                if last_mes not in ["Yes", "Go back"]:
                    await update.message.reply_text(
                        "You entered a wrong value!",
                        reply_markup=ReplyKeyboardMarkup([go_back_text], resize_keyboard=True, one_time_keyboard=True)
                    )
                    return SHOW_PROFILE
                
                cursor.execute("SELECT UserName, Age, Bio, Photo, Premium FROM Users WHERE PersonID = %s", (user_id,))
                user_name, user_age, user_bio, user_photo, user_premium = cursor.fetchone()
        
        message_text = f"{user_name}, {user_age}, {user_bio or 'None'} {'| Premium ❤️‍🔥' if user_premium > 0 else ''}"
        await update.message.reply_text("Your profile:")
        await update.message.reply_photo(user_photo or 'None', caption=message_text)
        await update.message.reply_text(
            "1. Edit My Profile.\n2. Change My Profile Picture.\n3. Edit My Bio.\n4. Start Viewing Profiles.",
            reply_markup=menu_markup
        )
        return MENU_EXE
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return SHOW_PROFILE

async def menu_exe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu options."""
    user_id = context.user_data.get('user_id')
    choice = update.message.text

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                
                cursor.execute("SELECT LikeUserID FROM Likes WHERE LikedUserID = %s", (user_id,))
                likes = cursor.fetchall()
                len_likes = len(likes)
        
        current_jobs = context.job_queue.get_jobs_by_name("dgc")
        for job in current_jobs:
            job.schedule_removal()

        if choice == "1":
            await update.message.reply_text("What is your name?")
            return AGE
        elif choice == "2":
            await update.message.reply_text(
                "Send your photo👍 for other users to see",
                reply_markup=ReplyKeyboardMarkup([leave_photo_choice], resize_keyboard=True, one_time_keyboard=True)
            )
            return SAVEPHOTO
        elif choice == "3":
            await update.message.reply_text(
                "Tell more about yourself. Who are you looking for? What do you want to do? I'll find the best matches.",
                reply_markup=ReplyKeyboardMarkup([leave_text_choice], resize_keyboard=True, one_time_keyboard=True)
            )
            return CHANGEBIO
        elif choice == "4":
            await update.message.reply_text(
                "Are you ready to see profiles? 🥰",
                reply_markup=ReplyKeyboardMarkup([yes_text], resize_keyboard=True, one_time_keyboard=True)
            )
            is_spam(user_id)
            return MATCHING
        elif choice == "Show." and len_likes > 0:
            with connection_pool.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT PersonID, UserName, Age, Bio, Photo FROM Users JOIN Likes ON PersonID = LikeUserID WHERE LikedUserID = %s",
                        (user_id,)
                    )
                    liked_users = cursor.fetchall()[0]
                    userid, user_name, user_age, user_bio, user_photo = liked_users
                    cursor.execute(
                        "SELECT MesToPerson FROM Likes WHERE LikeUserID = %s AND LikedUserID = %s",
                        (userid, user_id)
                    )
                    mes_to_person = cursor.fetchone()[0]
            
            message_text = f"{user_name}, {user_age}, {user_bio or 'None'}\n\n\nThis person has a message for you:\n{mes_to_person}" if mes_to_person and mes_to_person != 'None' else f"{user_name}, {user_age}, {user_bio or 'None'}"
            await update.message.reply_photo(user_photo, caption=message_text, reply_markup=like_or_not_markup)
            return SHOW_WHO_LIKES
        elif choice == "Not searching anymore." and len_likes > 0:
            await update.message.reply_text(
                "You won't know who likes you then... Sure about deactivating?\n\n1. Yes, deactivate my profile please.\n2. No, I want to see my matches.",
                reply_markup=show_n_not_show_markup
            )
            return DEACTIVE
        elif choice == "/report":
            await update.message.reply_text("Works only on someone's profile")
            return MENU_EXE
        else:
            await update.message.reply_text("You entered an incorrect value!", reply_markup=menu_markup)
            return MENU_EXE
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return MENU_EXE

async def wait_menu_exe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle wait menu options."""
    user_id = context.user_data.get('user_id')
    choice = update.message.text

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
        
        if choice == "1":
            await update.message.reply_text(
                "Are you ready to see profiles? �0",
                reply_markup=ReplyKeyboardMarkup([yes_text], resize_keyboard=True, one_time_keyboard=True)
            )
            return MATCHING
        elif choice == "2":
            with connection_pool.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT UserName, Age, Bio, Photo, Premium FROM Users WHERE PersonID = %s", (user_id,))
                    user_name, user_age, user_bio, user_photo, user_premium = cursor.fetchone()
            
            message_text = f"{user_name}, {user_age}, {user_bio or 'None'} {'| Premium ❤️‍🔥' if user_premium > 0 else ''}"
            await update.message.reply_text("Your profile:")
            await update.message.reply_photo(user_photo or 'None', caption=message_text)
            await update.message.reply_text(
                "1. Edit My Profile.\n2. Change My Profile Picture.\n3. Edit My Bio.\n4. Start Viewing Profiles.",
                reply_markup=menu_markup
            )
            return MENU_EXE
        elif choice == "3":
            await update.message.reply_text(
                "You won't know who likes you then... Sure about deactivating?\n\n1. Yes, deactivate my profile please.\n2. No, I want to see my matches.",
                reply_markup=show_n_not_show_markup
            )
            return DEACTIVE
        elif choice == "/report":
            await update.message.reply_text("Works only on someone's profile")
            return WAIT_MENU_EXE
        else:
            await update.message.reply_text("You entered an incorrect value!", reply_markup=wait_menu_markup)
            return WAIT_MENU_EXE
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return WAIT_MENU_EXE

async def matching(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle profile matching and likes."""
    user_id = context.user_data.get('user_id')
    last_mes = update.message.text

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                
                cursor.execute("SELECT LikeUserID FROM Likes WHERE LikedUserID = %s", (user_id,))
                likes = cursor.fetchall()
                len_likes = len(likes)
        
        if is_spam(user_id):
            await update.message.reply_text("You're sending messages too quickly. Temporarily banned.")
            return MATCHING

        current_jobs = context.job_queue.get_jobs_by_name("dgc")
        for job in current_jobs:
            job.schedule_removal()

        async def check_who_likes(context: ContextTypes.DEFAULT_TYPE):
            try:
                with connection_pool.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT LikeUserID FROM Likes WHERE LikedUserID = %s", (user_id,))
                        likes = cursor.fetchall()
                        len_likes = len(likes)
                        last_len = user_last_len.get(user_id, 0)
                        if len_likes > 0 and last_len != len_likes:
                            user_last_len[user_id] = len_likes
                            await update.message.reply_text(
                                f"{len_likes} person liked you. Have a look?\n\n1. Show.\n2. Not searching anymore.",
                                reply_markup=ReplyKeyboardMarkup([show_who_likes_choice], resize_keyboard=True, one_time_keyboard=True)
                            )
                            context.job.data = True
            except mysql.connector.Error:
                pass
            await asyncio.sleep(1)

        context.job_queue.run_repeating(check_who_likes, interval=10, first=0, name="dgc")

        if len_likes > 0:
            if last_mes == "Show.":
                with connection_pool.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "SELECT PersonID, UserName, Age, Bio, Photo FROM Users JOIN Likes ON PersonID = LikeUserID WHERE LikedUserID = %s",
                            (user_id,)
                        )
                        liked_users = cursor.fetchall()[0]
                        userid, user_name, user_age, user_bio, user_photo = liked_users
                        cursor.execute(
                            "SELECT MesToPerson FROM Likes WHERE LikeUserID = %s AND LikedUserID = %s",
                            (userid, user_id)
                        )
                        mes_to_person = cursor.fetchone()[0]
                
                message_text = f"{user_name}, {user_age}, {user_bio or 'None'}\n\n\nThis person has a message for you:\n{mes_to_person}" if mes_to_person and mes_to_person != 'None' else f"{user_name}, {user_age}, {user_bio or 'None'}"
                await update.message.reply_photo(user_photo, caption=message_text, reply_markup=like_or_not_markup)
                return SHOW_WHO_LIKES
            elif last_mes == "Not searching anymore.":
                await update.message.reply_text(
                    "You won't know who likes you then... Sure about deactivating?\n\n1. Yes, deactivate my profile please.\n2. No, I want to see my matches.",
                    reply_markup=show_n_not_show_markup
                )
                user_last_len[user_id] = 0
                return DEACTIVE

        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT DailyViewCount, Premium FROM Users WHERE PersonID = %s", (user_id,))
                view_count, user_premium = cursor.fetchone()
        
        if view_count > 0 or user_premium > 0:
            liked_user_id = context.user_data.get('liked_user_id')
            try:
                with connection_pool.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT UserName, Age, Bio, Photo FROM Users WHERE PersonID = %s", (user_id,))
                        user_name, user_age, user_bio, user_photo = cursor.fetchone()
                        
                        if last_mes == "❤️":
                            cursor.execute("SELECT * FROM Likes WHERE LikeUserID = %s AND LikedUserID = %s", (user_id, liked_user_id))
                            if not cursor.fetchone():
                                cursor.execute("INSERT INTO Likes (LikeUserID, LikedUserID) VALUES (%s, %s)", (user_id, liked_user_id))
                                conn.commit()
                        elif last_mes == "💌" and context.user_data.get('flag_user'):
                            context.user_data['mes_person_id'] = liked_user_id
                            await update.message.reply_text(
                                "Write a message for this user",
                                reply_markup=ReplyKeyboardMarkup([go_back_text], resize_keyboard=True, one_time_keyboard=True)
                            )
                            return SAVE_MESSAGE
                        elif last_mes == "👎":
                            pass
                        elif last_mes == "💤":
                            await update.message.reply_text(
                                "Wait until someone sees you.\n\n1. View profiles.\n2. My profile.\n3. Not searching anymore.",
                                reply_markup=wait_menu_markup
                            )
                            return WAIT_MENU_EXE
                        elif last_mes == "/report" and context.user_data.get('flag_user'):
                            context.user_data['rep_person_id'] = liked_user_id
                            await update.message.reply_text(
                                "Specify the reason.\n\n1. 🔞 Adult material.\n2. 💊 Drug propaganda.\n3. 💰 Sale of goods and services.\n4. 🦨 Others.\n***\n9. Go back.",
                                reply_markup=report_markup
                            )
                            return REPORT_USER
                        elif last_mes == "Yes" or last_mes == "Go back":
                            pass
                        else:
                            await update.message.reply_text("There is no such option.", reply_markup=like_markup)
                            return MATCHING
                        
                        cursor.execute("SELECT Looking, Gender FROM Users WHERE PersonID = %s", (user_id,))
                        looking, user_gender = cursor.fetchone()
                
                if looking == "Girls" and user_gender == "Male":
                    user_looking = "Boys"
                    match_gender = "Female"
                elif looking == "Boys" and user_gender == "Female":
                    user_looking = "Girls"
                    match_gender = "Male"
                elif looking == "Girls" and user_gender == "Female":
                    user_looking = "Girls"
                    match_gender = "Female"
                elif looking == "Boys" and user_gender == "Male":
                    user_looking = "Boys"
                    match_gender = "Male"
                else:
                    user_looking = "Girls"
                    match_gender = "Female"
                
                with connection_pool.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT Age FROM Users WHERE PersonID = %s AND Bio IS NOT NULL AND Photo IS NOT NULL", (user_id,))
                        my_user_age = cursor.fetchone()[0]
                        cursor.execute(
                            "SELECT COUNT(*) FROM Users WHERE Gender = %s AND Looking = %s AND IsActive = 1 AND PersonID NOT IN (SELECT LikedUserID FROM Likes WHERE LikeUserID = %s) AND Age BETWEEN %s AND %s AND PersonID != %s AND Bio IS NOT NULL AND Photo IS NOT NULL",
                            (match_gender, user_looking, user_id, my_user_age - 5, my_user_age + 5, user_id)
                        )
                        total_users = cursor.fetchone()[0]
                
                if total_users == 0:
                    await update.message.reply_text(
                        "Unable to find someone that meets your criteria at the moment. Please come back later and try again.☺",
                        reply_markup=ReplyKeyboardMarkup([go_back_text], resize_keyboard=True, one_time_keyboard=True)
                    )
                    return SHOW_PROFILE
                
                random_index = random.randint(0, total_users - 1)
                with connection_pool.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "SELECT PersonID, UserName, Age, Bio, Photo FROM Users WHERE Gender = %s AND Looking = %s AND IsActive = 1 AND PersonID NOT IN (SELECT LikedUserID FROM Likes WHERE LikeUserID = %s) AND Age BETWEEN %s AND %s AND Bio IS NOT NULL AND Photo IS NOT NULL LIMIT 1 OFFSET %s",
                            (match_gender, user_looking, user_id, my_user_age - 5, my_user_age + 5, random_index)
                        )
                        random_user = cursor.fetchone()
                        userid, user_name, user_age, user_bio, user_photo = random_user
                        context.user_data['liked_user_id'] = userid
                        context.user_data['flag_user'] = userid
                        message_text = f"{user_name}, {user_age}, {user_bio or 'None'}"
                        await update.message.reply_photo(user_photo, caption=message_text, reply_markup=like_markup)
                
                if user_premium == 0:
                    with connection_pool.get_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("UPDATE Users SET DailyViewCount = DailyViewCount - 1 WHERE PersonID = %s", (user_id,))
                            conn.commit()
                
                return MATCHING
            except mysql.connector.Error:
                await context.bot.send_message(user_id, "Database error. Please try again.")
                return MATCHING
        else:
            await update.message.reply_text(
                "You have reached the daily liking limit. Please come back in 24 hours.",
                reply_markup=ReplyKeyboardMarkup([go_back_text], resize_keyboard=True, one_time_keyboard=True)
            )
            return SHOW_PROFILE
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return MATCHING

async def save_the_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save a message to another user."""
    user_id = context.user_data.get('user_id')
    mes_person_id = context.user_data.get('mes_person_id')
    last_mes = update.message.text

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                
                if last_mes == "Go back":
                    cursor.execute("SELECT PersonID, UserName, Age, Bio, Photo FROM Users WHERE PersonID = %s", (mes_person_id,))
                    userid, user_name, user_age, user_bio, user_photo = cursor.fetchone()
                    message_text = f"{user_name}, {user_age}, {user_bio or 'None'}"
                    await update.message.reply_photo(user_photo, caption=message_text, reply_markup=like_markup)
                    return MATCHING
                
                mes_to_person = last_mes
                if not mes_to_person or mes_to_person == 'None':
                    await update.message.reply_text("You entered an incorrect value!")
                    return SAVE_MESSAGE
                
                cursor.execute("INSERT INTO Likes (LikeUserID, LikedUserID, MesToPerson) VALUES (%s, %s, %s)", (user_id, mes_person_id, mes_to_person))
                conn.commit()
        
        await update.message.reply_text(
            "Shall we continue to view profiles? 🥰",
            reply_markup=ReplyKeyboardMarkup([yes_text], resize_keyboard=True, one_time_keyboard=True)
        )
        return MATCHING
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return SAVE_MESSAGE

async def report_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user reporting."""
    user_id = context.user_data.get('user_id')
    rep_person_id = context.user_data.get('rep_person_id')
    last_mes = update.message.text

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                
                if last_mes == "9":
                    cursor.execute("SELECT PersonID, UserName, Age, Bio, Photo FROM Users WHERE PersonID = %s", (rep_person_id,))
                    userid, user_name, user_age, user_bio, user_photo = cursor.fetchone()
                    message_text = f"{user_name}, {user_age}, {user_bio or 'None'}"
                    await update.message.reply_photo(user_photo, caption=message_text, reply_markup=like_markup)
                    return MATCHING
                
                if last_mes not in ["1🔞", "2💊", "3💰", "4🦨"]:
                    await update.message.reply_text("You entered an incorrect value!")
                    return REPORT_USER
                
                cursor.execute("SELECT COUNT(*) FROM Reports WHERE UserID = %s", (rep_person_id,))
                row_count = cursor.fetchone()[0]
                
                if last_mes == "1🔞":
                    if row_count > 0:
                        cursor.execute("UPDATE Reports SET AdultREP = AdultREP + 1 WHERE UserID = %s", (rep_person_id,))
                    else:
                        cursor.execute("INSERT INTO Reports (UserID, AdultREP) VALUES (%s, 1)", (rep_person_id,))
                elif last_mes == "2💊":
                    if row_count > 0:
                        cursor.execute("UPDATE Reports SET DrugREP = DrugREP + 1 WHERE UserID = %s", (rep_person_id,))
                    else:
                        cursor.execute("INSERT INTO Reports (UserID, DrugREP) VALUES (%s, 1)", (rep_person_id,))
                elif last_mes == "3💰":
                    if row_count > 0:
                        cursor.execute("UPDATE Reports SET SaleREP = SaleREP + 1 WHERE UserID = %s", (rep_person_id,))
                    else:
                        cursor.execute("INSERT INTO Reports (UserID, SaleREP) VALUES (%s, 1)", (rep_person_id,))
                elif last_mes == "4🦨":
                    if row_count > 0:
                        cursor.execute("UPDATE Reports SET OtherREP = OtherREP + 1 WHERE UserID = %s", (rep_person_id,))
                    else:
                        cursor.execute("INSERT INTO Reports (UserID, OtherREP) VALUES (%s, 1)", (rep_person_id,))
                conn.commit()
        
        await update.message.reply_text(
            "Shall we continue to view profiles? 🥰",
            reply_markup=ReplyKeyboardMarkup([yes_text], resize_keyboard=True, one_time_keyboard=True)
        )
        return MATCHING
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return REPORT_USER

async def de_active_or_not(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle profile deactivation."""
    user_id = context.user_data.get('user_id')
    choice = update.message.text

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                
                if is_spam(user_id):
                    await update.message.reply_text("You're sending messages too quickly. Temporarily banned.")
                    return DEACTIVE
                
                if choice == "1":
                    cursor.execute("UPDATE Users SET IsActive = 0 WHERE PersonID = %s", (user_id,))
                    conn.commit()
                    await update.message.reply_text(
                        "Hope you met someone with my help!\nAlways happy to chat. If bored, text me - I'll find someone special for you.\n1. View profiles",
                        reply_markup=ReplyKeyboardMarkup([show_profiles], resize_keyboard=True, one_time_keyboard=True)
                    )
                    return NONEACTIVE
                elif choice == "2":
                    cursor.execute("SELECT UserName, Age, Bio, Photo, Premium FROM Users WHERE PersonID = %s", (user_id,))
                    user_name, user_age, user_bio, user_photo, user_premium = cursor.fetchone()
                    message_text = f"{user_name}, {user_age}, {user_bio or 'None'} {'| Premium ❤️‍🔥' if user_premium > 0 else ''}"
                    await update.message.reply_text("Your profile:")
                    await update.message.reply_photo(user_photo or 'None', caption=message_text)
                    await update.message.reply_text(
                        "1. Edit My Profile.\n2. Change My Profile Picture.\n3. Edit My Bio.\n4. Start Viewing Profiles.",
                        reply_markup=menu_markup
                    )
                    return MENU_EXE
                else:
                    await update.message.reply_text("You entered an incorrect value!", reply_markup=show_n_not_show_markup)
                    return DEACTIVE
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return DEACTIVE

async def not_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inactive user state."""
    user_id = context.user_data.get('user_id')
    last_mes = update.message.text

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                
                if is_spam(user_id):
                    await update.message.reply_text("You're sending messages too quickly. Temporarily banned.")
                    return NONEACTIVE
                
                if last_mes == "View profiles.":
                    cursor.execute("UPDATE Users SET IsActive = 1 WHERE PersonID = %s", (user_id,))
                    conn.commit()
                    cursor.execute("SELECT UserName, Age, Bio, Photo, Premium FROM Users WHERE PersonID = %s", (user_id,))
                    user_name, user_age, user_bio, user_photo, user_premium = cursor.fetchone()
                    message_text = f"{user_name}, {user_age}, {user_bio or 'None'} {'| Premium ❤️‍🔥' if user_premium > 0 else ''}"
                    await update.message.reply_text("Your profile:")
                    await update.message.reply_photo(user_photo or 'None', caption=message_text)
                    await update.message.reply_text(
                        "1. Edit My Profile.\n2. Change My Profile Picture.\n3. Edit My Bio.\n4. Start Viewing Profiles.",
                        reply_markup=menu_markup
                    )
                    return MENU_EXE
                else:
                    await update.message.reply_text(
                        "You entered an incorrect value!",
                        reply_markup=ReplyKeyboardMarkup([show_profiles], resize_keyboard=True, one_time_keyboard=True)
                    )
                    return NONEACTIVE
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return NONEACTIVE

async def show_who_likes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show users who liked the current user."""
    user_id = context.user_data.get('user_id')

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
                
                if is_spam(user_id):
                    await update.message.reply_text("You're sending messages too quickly. Temporarily banned.")
                    return SHOW_WHO_LIKES
                
                cursor.execute("SELECT LikeUserID FROM Likes WHERE LikedUserID = %s", (user_id,))
                likes = cursor.fetchall()
                len_likes = len(likes)
                
                if len_likes == 0:
                    await update.message.reply_text(
                        "That's all for now. Move on?",
                        reply_markup=ReplyKeyboardMarkup([yes_text], resize_keyboard=True, one_time_keyboard=True)
                    )
                    return SHOW_PROFILE
                
                cursor.execute(
                    "SELECT PersonID, UserName, Age, Bio, Photo FROM Users JOIN Likes ON PersonID = LikeUserID WHERE LikedUserID = %s",
                    (user_id,)
                )
                liked_users = cursor.fetchall()[0]
                userid, user_name, user_age, user_bio, user_photo = liked_users
                
                cursor.execute(
                    "SELECT MesToPerson FROM Likes WHERE LikeUserID = %s AND LikedUserID = %s",
                    (userid, user_id)
                )
                mes_to_person = cursor.fetchone()[0]
                
                cursor.execute("SELECT PersonID, UserName, Age, Bio, Photo FROM Users WHERE PersonID = %s", (user_id,))
                my_userid, my_user_name, my_user_age, my_user_bio, my_user_photo = cursor.fetchone()
                
                last_mes = update.message.text
                if last_mes == "❤️":
                    await context.bot.send_photo(user_id, user_photo, caption=f"{user_name}, {user_age}, {user_bio or 'None'}")
                    await update.message.reply_text(
                        f"Excellent! Hope you'll have a good time ;)\n\nStart chatting 👉 <a href='tg://user?id={userid}'>{user_name}</a>",
                        parse_mode='HTML'
                    )
                    await context.bot.send_photo(userid, my_user_photo, caption=f"{my_user_name}, {my_user_age}, {my_user_bio or 'None'}")
                    await context.bot.send_message(
                        userid,
                        f"Excellent! Hope you'll have a good time ;)\n\nStart chatting 👉 <a href='tg://user?id={my_userid}'>{my_user_name}</a>",
                        parse_mode='HTML'
                    )
                    cursor.execute("DELETE FROM Likes WHERE LikeUserID = %s AND LikedUserID = %s", (userid, user_id))
                    cursor.execute("DELETE FROM Likes WHERE LikedUserID = %s AND LikeUserID = %s", (user_id, userid))
                    conn.commit()
                    return SHOW_WHO_LIKES
                elif last_mes == "👎":
                    cursor.execute("DELETE FROM Likes WHERE LikeUserID = %s AND LikedUserID = %s", (userid, user_id))
                    conn.commit()
                    return SHOW_WHO_LIKES
                
                message_text = f"{user_name}, {user_age}, {user_bio or 'None'}\n\n\nThis person has a message for you:\n{mes_to_person}" if mes_to_person and mes_to_person != 'None' else f"{user_name}, {user_age}, {user_bio or 'None'}"
                await update.message.reply_photo(user_photo, caption=message_text, reply_markup=like_or_not_markup)
                return SHOW_WHO_LIKES
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return SHOW_WHO_LIKES

async def premium_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle premium subscription purchase."""
    user_id = context.user_data.get('user_id')
    choice = update.message.text

    try:
        with connection_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banned WHERE PersonID = %s", (user_id,))
                if cursor.fetchone():
                    await context.bot.send_message(user_id, "You are banned!")
                    return BANNED
        
        if choice == "1 Month":
            price = '999'
        elif choice == "6 Months":
            price = '3999'
        elif choice == "1 Year":
            price = '4999'
        elif choice == "Go back":
            with connection_pool.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT UserName, Age, Bio, Photo, Premium FROM Users WHERE PersonID = %s", (user_id,))
                    user_name, user_age, user_bio, user_photo, user_premium = cursor.fetchone()
            
            message_text = f"{user_name}, {user_age}, {user_bio or 'None'} {'| Premium ❤️‍🔥' if user_premium > 0 else ''}"
            await update.message.reply_text("Your profile:")
            await update.message.reply_photo(user_photo or 'None', caption=message_text)
            await update.message.reply_text(
                "1. Edit My Profile.\n2. Change My Profile Picture.\n3. Edit My Bio.\n4. Start Viewing Profiles.",
                reply_markup=menu_markup
            )
            return MENU_EX
        else:
            await update.message.reply_text(
                "You entered an incorrect value!",
                reply_markup=ReplyKeyboardMarkup([pay_choice], resize_keyboard=True, one_time_keyboard=True)
            )
            return PREMIUM
        
        formatted_link = pay(user_id=user_id, price=price)  # Placeholder: Implement pay function
        await context.bot.send_message(
            user_id,
            f"Please follow the link to make the purchase\n\n👉 <a href='{formatted_link}'>StanbulDatePremium 🛍</a>",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup([go_back_text], resize_keyboard=True, one_time_keyboard=True)
        )
        return SHOW_PROFILE
    except mysql.connector.Error as e:
        await context.bot.send_message(user_id, "Database error. Please try again.")
        return PREMIUM

async def banned_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle banned users."""
    await update.message.reply_text("You are banned!")
    return BANNED

def main():
    """Run the bot."""
    req = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )
    app = Application.builder().token(TOKEN).request(req).build()

    # Log DB status on startup
    if is_db_connected():
        logger.info("Database connection OK on startup")
    else:
        logger.warning("Database connection FAILED on startup")

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, check_user_state),
            CommandHandler("start", start_command),
        ],
        states={
            CHECK_USER_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_user_state)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_command)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_age)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_gender)],
            LOOKING: [MessageHandler(filters.Regex("^(Male|Female)$"), set_looking)],
            CITY: [MessageHandler(filters.Regex("^(Boys|Girls)$"), set_city)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_bio)],
            CHANGEBIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, change_bio)],
            PHOTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_photo)],
            SAVEPHOTO: [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, save_photo)],
            SAVE_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_the_message)],
            SHOW_PROFILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_profile)],
            MENU_EXE: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_exe)],
            WAIT_MENU_EXE: [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_menu_exe)],
            MATCHING: [MessageHandler(filters.TEXT & ~filters.COMMAND, matching)],
            DEACTIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, de_active_or_not)],
            NONEACTIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, not_active)],
            SHOW_WHO_LIKES: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_who_likes)],
            REPORT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_user)],
            PREMIUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, premium_sale)],
            BANNED: [MessageHandler(filters.TEXT & ~filters.COMMAND, banned_user)]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^View profiles$"), show_profile)
        ]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("db", db_status))
    app.add_error_handler(on_error)
    app.run_polling()

if __name__ == "__main__":
    main()