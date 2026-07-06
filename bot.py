import discord
from discord import ui, app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import os
import sys
import json
import logging
from dotenv import load_dotenv

load_dotenv()

# ---------- НАСТРОЙКИ ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_CHANNEL_ID = int(os.getenv("ALLOWED_CHANNEL_ID", 1518300754883121183))
EVENT_CHANNEL_ID = int(os.getenv("EVENT_CHANNEL_ID", 1514772518408556706))
ALLOWED_ROLE_ID = int(os.getenv("ALLOWED_ROLE_ID", 1479864014522814544))
MENTION_ROLE_ID = int(os.getenv("MENTION_ROLE_ID", 1381292929628242121))
TICKET_CREATE_CHANNEL_ID = int(os.getenv("TICKET_CREATE_CHANNEL_ID", 1518385240626823250))
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", 1518372992160366602))
TICKET_ARCHIVE_CATEGORY_ID = int(os.getenv("TICKET_ARCHIVE_CATEGORY_ID", 1518376110855946250))
TICKET_NOTIFY_ROLE_ID = int(os.getenv("TICKET_NOTIFY_ROLE_ID", 1399839231181852833))
OWNER_ID = int(os.getenv("OWNER_ID", 949706441319653486))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 1518841652666437793))
BLACKLIST_CHANNEL_ID = int(os.getenv("BLACKLIST_CHANNEL_ID", 1436774543338504332))

# ---------- НАСТРОЙКА ЛОГГЕРА ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs.txt", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("HOFMAN_BOT")

# Категории и цвета для embed-логов
LOG_CATEGORIES = {
    "сбор": discord.Color.green(),
    "тикет": discord.Color.gold(),
    "админ": discord.Color.purple(),
    "система": discord.Color.blue(),
    "ошибка": discord.Color.red(),
    "чс": discord.Color.dark_red()
}

async def log_action(
    guild: discord.Guild,
    action: str,
    user: discord.Member = None,
    details: str = "",
    category: str = "система",
    color: discord.Color = None
):
    """
    Улучшенное логирование: категории, цвета, дублирование в файл.
    """
    if color is None:
        color = LOG_CATEGORIES.get(category, discord.Color.blue())

    channel = bot.get_channel(LOG_CHANNEL_ID)
    
    embed = discord.Embed(
        title=f"📋 {category.upper()}",
        description=(
            f"**Действие:** {action}\n"
            f"**Пользователь:** {user.mention if user else 'Система'}\n"
            f"**Детали:** {details}"
        ),
        color=color,
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"ID: {user.id if user else 'Система'} | Сервер: {guild.name if guild else 'N/A'}")

    if channel:
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Не удалось отправить лог в канал: {e}")

    log_line = (
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"Категория: {category} | "
        f"Действие: {action} | "
        f"Пользователь: {user.display_name if user else 'Система'} (ID: {user.id if user else 'N/A'}) | "
        f"Детали: {details} | "
        f"Сервер: {guild.name if guild else 'N/A'}"
    )
    logger.info(log_line)

# ---------- ИНИЦИАЛИЗАЦИЯ БОТА ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- ХРАНИЛИЩА ----------
events = {}
tickets = {}

# ---------- КЛАСС СОБЫТИЯ ----------
class EventData:
    def __init__(self, title, date_str, time_str, description, creator_id, max_participants, channel_id, message_id):
        self.title = title
        self.date_str = date_str
        self.time_str = time_str
        self.description = description
        self.creator_id = creator_id
        self.max_participants = max_participants
        self.channel_id = channel_id
        self.message_id = message_id
        self.participants = set()
        self.checked = set()

    def get_formatted_datetime(self):
        dt = datetime.strptime(f"{self.date_str} {self.time_str}", "%d.%m.%Y %H:%M")
        weekdays = {
            0: "понедельник", 1: "вторник", 2: "среда",
            3: "четверг", 4: "пятница", 5: "суббота", 6: "воскресенье"
        }
        months = {
            1: "января", 2: "февраля", 3: "марта",
            4: "апреля", 5: "мая", 6: "июня",
            7: "июля", 8: "августа", 9: "сентября",
            10: "октября", 11: "ноября", 12: "декабря"
        }
        weekday = weekdays[dt.weekday()]
        month = months[dt.month]
        return f"{weekday}, {dt.day} {month} {dt.year} г. {dt.strftime('%H:%M')}"

# ---------- МОДАЛЬНОЕ ОКНО СОБЫТИЯ ----------
class EventModal(ui.Modal, title="📅 Создание сбора реакций"):
    event_title = ui.TextInput(
        label="📌 Название сбора",
        placeholder="Например: ПИКАЕМ ПОСТАВКУ",
        required=True,
        max_length=100
    )
    date = ui.TextInput(
        label="📆 Дата (дд.мм.гггг)",
        placeholder="Например: 21.06.2026",
        required=True,
        max_length=10
    )
    time = ui.TextInput(
        label="⏰ Время (чч:мм)",
        placeholder="Например: 13:30",
        required=True,
        max_length=5
    )
    max_participants = ui.TextInput(
        label="👥 Максимум участников",
        placeholder="Например: 30 (число от 1 до 100)",
        required=True,
        max_length=3
    )
    description = ui.TextInput(
        label="📝 Дополнительное сообщение",
        placeholder="Опишите детали (необязательно)",
        required=False,
        max_length=500,
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        date_str = self.date.value.strip()
        try:
            datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError:
            await interaction.response.send_message("❌ Неверный формат даты! Используйте **дд.мм.гггг** (например, 21.06.2026).", ephemeral=True)
            return
        time_str = self.time.value.strip()
        try:
            datetime.strptime(time_str, "%H:%M")
        except ValueError:
            await interaction.response.send_message("❌ Неверный формат времени! Используйте **чч:мм** (например, 13:30).", ephemeral=True)
            return
        max_val = self.max_participants.value.strip()
        if not max_val.isdigit():
            await interaction.response.send_message("❌ Максимум участников должно быть целым числом.", ephemeral=True)
            return
        max_participants = int(max_val)
        if max_participants < 1 or max_participants > 100:
            await interaction.response.send_message("❌ Максимум участников должно быть от 1 до 100.", ephemeral=True)
            return
        channel = bot.get_channel(EVENT_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("❌ Ошибка: канал для событий не найден.", ephemeral=True)
            return
        title_val = self.event_title.value.strip()
        desc_val = self.description.value.strip() or "Без дополнительного описания"
        event = EventData(
            title=title_val,
            date_str=date_str,
            time_str=time_str,
            description=desc_val,
            creator_id=interaction.user.id,
            max_participants=max_participants,
            channel_id=EVENT_CHANNEL_ID,
            message_id=None
        )
        event.participants.add(interaction.user.id)
        embed = await self.build_embed(event, interaction.guild)
        view = EventView()
        view.event = event
        mention = f"<@&{MENTION_ROLE_ID}>"
        message = await channel.send(content=mention, embed=embed, view=view)
        event.message_id = message.id
        events[message.id] = event
        await interaction.response.send_message(f"✅ Сбор **«{title_val}»** создан! Перейдите в канал {channel.mention}", ephemeral=True)
        await log_action(interaction.guild, "Создание сбора", interaction.user, f"Название: {title_val}, Дата: {date_str}, Время: {time_str}", category="сбор")

    async def build_embed(self, event: EventData, guild: discord.Guild):
        creator = guild.get_member(event.creator_id)
        creator_mention = creator.mention if creator else f"<@{event.creator_id}>"
        formatted_dt = event.get_formatted_datetime()
        participants_list = []
        for uid in event.participants:
            member = guild.get_member(uid)
            name = member.display_name if member else f"<@{uid}>"
            if uid in event.checked:
                participants_list.append(f"{name} ✅")
            else:
                participants_list.append(name)
        table = "\n".join(participants_list) if participants_list else "Нет участников"
        count = len(event.participants)
        embed = discord.Embed(
            title=f"{event.title}",
            description=(
                f"**Создал:** {creator_mention}\n"
                f"**Дата:** {formatted_dt}\n"
                f"**Роли:** Без ограничений\n\n"
                f"**Участники ({count}/{event.max_participants})**\n"
                f"{table}"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="✅ - отметился")
        return embed

# ---------- УПРАВЛЕНИЕ СОБЫТИЕМ ----------
class EventView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.event = None

    @ui.button(label="Присоединиться", style=discord.ButtonStyle.success, custom_id="event_join")
    async def join_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.event:
            await interaction.response.send_message("❌ Ошибка: событие не найдено.", ephemeral=True)
            return
        user_id = interaction.user.id
        if user_id in self.event.participants:
            await interaction.response.send_message("Вы уже в списке участников.", ephemeral=True)
            return
        if len(self.event.participants) >= self.event.max_participants:
            await interaction.response.send_message(f"❌ Достигнуто максимальное количество участников ({self.event.max_participants}).", ephemeral=True)
            return
        self.event.participants.add(user_id)
        await self.update_event(interaction)
        await log_action(interaction.guild, "Присоединение к сбору", interaction.user, f"Сбор: {self.event.title}", category="сбор")

    @ui.button(label="Покинуть", style=discord.ButtonStyle.danger, custom_id="event_leave")
    async def leave_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.event:
            await interaction.response.send_message("❌ Ошибка: событие не найдено.", ephemeral=True)
            return
        user_id = interaction.user.id
        if user_id not in self.event.participants:
            await interaction.response.send_message("Вы не в списке участников.", ephemeral=True)
            return
        self.event.participants.discard(user_id)
        self.event.checked.discard(user_id)
        await self.update_event(interaction)
        await log_action(interaction.guild, "Выход из сбора", interaction.user, f"Сбор: {self.event.title}", category="сбор")

    @ui.button(label="Отметиться", style=discord.ButtonStyle.primary, custom_id="event_check")
    async def check_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.event:
            await interaction.response.send_message("❌ Ошибка: событие не найдено.", ephemeral=True)
            return
        user_id = interaction.user.id
        if user_id not in self.event.participants:
            await interaction.response.send_message("Сначала присоединитесь к сбору!", ephemeral=True)
            return
        if user_id in self.event.checked:
            self.event.checked.remove(user_id)
            status = "отметка снята"
        else:
            self.event.checked.add(user_id)
            status = "отметился"
        await self.update_event(interaction)
        await log_action(interaction.guild, f"Изменение отметки ({status})", interaction.user, f"Сбор: {self.event.title}", category="сбор")

    async def update_event(self, interaction: discord.Interaction):
        guild = interaction.guild
        creator = guild.get_member(self.event.creator_id)
        creator_mention = creator.mention if creator else f"<@{self.event.creator_id}>"
        formatted_dt = self.event.get_formatted_datetime()
        participants_list = []
        for uid in self.event.participants:
            member = guild.get_member(uid)
            name = member.display_name if member else f"<@{uid}>"
            if uid in self.event.checked:
                participants_list.append(f"{name} ✅")
            else:
                participants_list.append(name)
        table = "\n".join(participants_list) if participants_list else "Нет участников"
        count = len(self.event.participants)
        embed = discord.Embed(
            title=f"{self.event.title}",
            description=(
                f"**Создал:** {creator_mention}\n"
                f"**Дата:** {formatted_dt}\n"
                f"**Роли:** Без ограничений\n\n"
                f"**Участники ({count}/{self.event.max_participants})**\n"
                f"{table}"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="✅ - отметился")
        channel = bot.get_channel(self.event.channel_id)
        if channel:
            try:
                message = await channel.fetch_message(self.event.message_id)
                await message.edit(embed=embed, view=self)
            except:
                pass
        await interaction.response.defer()

# ---------- СТАТИСТИКА ----------
class StatsView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="Обновить", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(embed=await get_stats_embed(interaction.guild), view=self)

async def get_stats_embed(guild: discord.Guild):
    total_members = guild.member_count
    humans = sum(1 for m in guild.members if not m.bot)
    bots = total_members - humans
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    categories = len(guild.categories)
    roles = len(guild.roles) - 1
    try:
        bans = [entry async for entry in guild.bans()]
        ban_count = len(bans)
    except discord.Forbidden:
        ban_count = "❌ Нет прав"
    created_at = guild.created_at.strftime("%d.%m.%Y %H:%M")
    embed = discord.Embed(title=f"📊 Статистика сервера: {guild.name}", color=discord.Color.blue())
    embed.add_field(name="👥 Всего участников", value=f"{total_members}", inline=True)
    embed.add_field(name="🧑 Людей", value=f"{humans}", inline=True)
    embed.add_field(name="🤖 Ботов", value=f"{bots}", inline=True)
    embed.add_field(name="🚫 Забанено", value=f"{ban_count}", inline=True)
    embed.add_field(name="📁 Категорий", value=f"{categories}", inline=True)
    embed.add_field(name="💬 Текстовых каналов", value=f"{text_channels}", inline=True)
    embed.add_field(name="🔊 Голосовых каналов", value=f"{voice_channels}", inline=True)
    embed.add_field(name="🎭 Ролей (без @everyone)", value=f"{roles}", inline=True)
    embed.add_field(name="📅 Сервер создан", value=f"{created_at}", inline=True)
    embed.set_footer(text=f"Запрошено • {datetime.now().strftime('%H:%M:%S')}")
    return embed

# ---------- ТИКЕТЫ ----------
class TransferSelectView(ui.View):
    def __init__(self, channel: discord.TextChannel, members: list):
        super().__init__(timeout=60)
        self.channel = channel
        options = []
        for member in members:
            if member.bot:
                continue
            options.append(discord.SelectOption(
                label=member.display_name,
                value=str(member.id),
                description=member.name
            ))
        if len(options) > 25:
            options = options[:25]
        self.select = discord.ui.Select(
            placeholder="Выберите администратора",
            options=options,
            custom_id="transfer_select"
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        user_id = int(self.select.values[0])
        guild = interaction.guild
        user = guild.get_member(user_id)
        if not user:
            await interaction.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        channel = self.channel
        if channel.id in tickets:
            tickets[channel.id]["responsible"] = user.id
            await update_ticket_embed(channel)
            await interaction.response.send_message(f"✅ Тикет передан пользователю {user.mention}.", ephemeral=True)
            await interaction.message.delete()
            await log_action(interaction.guild, "Передача тикета", interaction.user, f"Тикет: {channel.mention} → {user.mention}", category="тикет")
        else:
            await interaction.response.send_message("❌ Тикет не найден в базе.", ephemeral=True)

async def update_ticket_embed(channel: discord.TextChannel):
    if channel.id not in tickets:
        return
    data = tickets[channel.id]
    author = channel.guild.get_member(data["author"])
    responsible = channel.guild.get_member(data["responsible"]) if data["responsible"] else None
    embed = discord.Embed(
        title="🎫 Тикет",
        description=(
            f"**Автор:** {author.mention if author else 'Неизвестен'}\n"
            f"**Ответственный:** {responsible.mention if responsible else 'Не назначен'}\n"
            f"**Статус:** {'✅ Взят' if responsible else '⏳ Ожидает'}\n\n"
            f"Опишите подробнее вашу проблему. Администраторы скоро ответят."
        ),
        color=discord.Color.green() if responsible else discord.Color.orange()
    )
    async for msg in channel.history(limit=1):
        if msg.author == bot.user:
            await msg.edit(embed=embed)
            break

class TicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Взять тикет", style=discord.ButtonStyle.success, custom_id="ticket_take")
    async def take_button(self, interaction: discord.Interaction, button: ui.Button):
        channel = interaction.channel
        if channel.category_id != TICKET_CATEGORY_ID:
            await interaction.response.send_message("❌ Этот тикет уже закрыт.", ephemeral=True)
            return
        role = interaction.guild.get_role(ALLOWED_ROLE_ID)
        if role is None or role not in interaction.user.roles:
            await interaction.response.send_message("❌ У вас нет прав брать тикеты.", ephemeral=True)
            return
        if channel.id in tickets and tickets[channel.id]["responsible"] is not None:
            await interaction.response.send_message("❌ Тикет уже взят другим администратором.", ephemeral=True)
            return
        if channel.id not in tickets:
            tickets[channel.id] = {"author": None, "responsible": None}
        tickets[channel.id]["responsible"] = interaction.user.id
        await update_ticket_embed(channel)
        await interaction.response.send_message("✅ Тикет взят вами.", ephemeral=True)
        await log_action(interaction.guild, "Взятие тикета", interaction.user, f"Тикет: {channel.mention}", category="тикет")

    @ui.button(label="Отдать обратно", style=discord.ButtonStyle.secondary, custom_id="ticket_return")
    async def return_button(self, interaction: discord.Interaction, button: ui.Button):
        channel = interaction.channel
        if channel.category_id != TICKET_CATEGORY_ID:
            await interaction.response.send_message("❌ Этот тикет уже закрыт.", ephemeral=True)
            return
        role = interaction.guild.get_role(ALLOWED_ROLE_ID)
        if role is None or role not in interaction.user.roles:
            await interaction.response.send_message("❌ У вас нет прав отдавать тикеты.", ephemeral=True)
            return
        if channel.id not in tickets or tickets[channel.id]["responsible"] is None:
            await interaction.response.send_message("❌ Тикет никому не назначен.", ephemeral=True)
            return
        tickets[channel.id]["responsible"] = None
        await update_ticket_embed(channel)
        await interaction.response.send_message("✅ Тикет возвращён в очередь.", ephemeral=True)
        await log_action(interaction.guild, "Возврат тикета", interaction.user, f"Тикет: {channel.mention}", category="тикет")

    @ui.button(label="Передать", style=discord.ButtonStyle.primary, custom_id="ticket_transfer")
    async def transfer_button(self, interaction: discord.Interaction, button: ui.Button):
        channel = interaction.channel
        if channel.category_id != TICKET_CATEGORY_ID:
            await interaction.response.send_message("❌ Этот тикет уже закрыт.", ephemeral=True)
            return
        role = interaction.guild.get_role(ALLOWED_ROLE_ID)
        if role is None or role not in interaction.user.roles:
            await interaction.response.send_message("❌ У вас нет прав передавать тикеты.", ephemeral=True)
            return
        members = [m for m in interaction.guild.members if role in m.roles and not m.bot and m.id != interaction.user.id]
        if not members:
            await interaction.response.send_message("❌ Нет доступных администраторов для передачи.", ephemeral=True)
            return
        view = TransferSelectView(channel, members)
        await interaction.response.send_message("Выберите администратора для передачи тикета:", view=view, ephemeral=True)

    @ui.button(label="Закрыть тикет", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: ui.Button):
        channel = interaction.channel
        if channel.category_id != TICKET_CATEGORY_ID:
            await interaction.response.send_message("❌ Этот тикет уже закрыт.", ephemeral=True)
            return
        role = interaction.guild.get_role(ALLOWED_ROLE_ID)
        if role is None or role not in interaction.user.roles:
            await interaction.response.send_message("❌ У вас нет прав закрывать тикеты.", ephemeral=True)
            return
        archive_category = interaction.guild.get_channel(TICKET_ARCHIVE_CATEGORY_ID)
        if not archive_category:
            await interaction.response.send_message("❌ Категория для архива не найдена.", ephemeral=True)
            return
        try:
            await channel.edit(category=archive_category)
            new_name = channel.name
            if not new_name.startswith("closed-"):
                new_name = f"closed-{new_name}"
                if len(new_name) > 100:
                    new_name = new_name[:100]
                await channel.edit(name=new_name)
            await interaction.response.send_message("✅ Тикет закрыт, перемещён в архив и переименован.")
            if channel.id in tickets:
                del tickets[channel.id]
            await log_action(interaction.guild, "Закрытие тикета", interaction.user, f"Тикет: {channel.mention}", category="тикет")
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)

# ---------- МОДАЛЬНОЕ ОКНО ТИКЕТА ----------
class TicketModal(ui.Modal, title="📩 Создание тикета"):
    ticket_title = ui.TextInput(
        label="📌 Название обращения",
        placeholder="Кратко о чём тикет",
        required=True,
        max_length=100
    )
    description = ui.TextInput(
        label="📝 Описание проблемы",
        placeholder="Подробно опишите суть",
        required=True,
        max_length=1000,
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not category:
            await interaction.response.send_message("❌ Категория для тикетов не найдена.", ephemeral=True)
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        admin_role = guild.get_role(ALLOWED_ROLE_ID)
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        channel_name = f"ticket-{interaction.user.display_name[:20]}"
        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=self.ticket_title.value
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка создания канала: {e}", ephemeral=True)
            return
        tickets[channel.id] = {"author": interaction.user.id, "responsible": None}
        embed = discord.Embed(
            title="🎫 Тикет",
            description=(
                f"**Автор:** {interaction.user.mention}\n"
                f"**Тема:** {self.ticket_title.value}\n"
                f"**Описание:**\n{self.description.value}\n\n"
                f"**Ответственный:** Не назначен\n"
                f"**Статус:** ⏳ Ожидает"
            ),
            color=discord.Color.orange()
        )
        view = TicketView()
        await channel.send(embed=embed, view=view)
        notify_role = guild.get_role(TICKET_NOTIFY_ROLE_ID)
        if notify_role:
            await channel.send(f"🔔 {notify_role.mention} – создан новый тикет!")
        await interaction.response.send_message(f"✅ Тикет создан! Вот ваш тикет: {channel.mention}", ephemeral=True)
        await log_action(interaction.guild, "Создание тикета", interaction.user, f"Тема: {self.ticket_title.value}, Канал: {channel.mention}", category="тикет")

class TicketCreateView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Создать тикет", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TicketModal())

# ---------- ГЛАВНАЯ ПАНЕЛЬ ----------
class MainPanel(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.channel_id != ALLOWED_CHANNEL_ID:
            await interaction.response.send_message("❌ Эта панель работает только в специальном канале.", ephemeral=True)
            return False
        role = interaction.guild.get_role(ALLOWED_ROLE_ID)
        if role is None or role not in interaction.user.roles:
            await interaction.response.send_message("❌ У вас нет прав для использования панели.", ephemeral=True)
            return False
        return True

    @ui.button(label="Создать сбор реакций", style=discord.ButtonStyle.primary, emoji="📖", custom_id="create_event")
    async def create_event_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(EventModal())

    @ui.button(label="Статистика сервера", style=discord.ButtonStyle.secondary, emoji="📊", custom_id="show_stats")
    async def stats_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = await get_stats_embed(interaction.guild)
        view = StatsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(label="Тикеты", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="ticket_panel")
    async def ticket_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TicketModal())

    @ui.button(label="📋 Чёрный список", style=discord.ButtonStyle.danger, custom_id="blacklist_link")
    async def blacklist_button(self, interaction: discord.Interaction, button: ui.Button):
        guild_id = interaction.guild.id
        channel_id = BLACKLIST_CHANNEL_ID
        url = f"https://discord.com/channels/{guild_id}/{channel_id}"
        await interaction.response.send_message(f"🔗 **Перейдите в канал чёрного списка:** {url}", ephemeral=True)
        await log_action(interaction.guild, "Переход по ссылке на ЧС", interaction.user, f"Канал: {url}", category="система")

# ---------- КОМАНДЫ ----------
@bot.tree.command(name="panel", description="Показать панель управления")
async def panel(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("❌ Команда доступна только в специальном канале.", ephemeral=True)
        return
    role = interaction.guild.get_role(ALLOWED_ROLE_ID)
    if role is None or role not in interaction.user.roles:
        await interaction.response.send_message("❌ У вас нет нужной роли.", ephemeral=True)
        return
    embed = discord.Embed(
        title="🔧 Панель управления HOFMAN FAMQ",
        description=(
            "Выберите нужное действие ниже 🚩\n\n"
            "🔗 **Инвайт в Hofman FAMQ:** https://discord.gg/uYQuCvdSn9\n"
            f"👑 **Создатель бота:** <@{OWNER_ID}>"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="HOFMAN FAMQ BOT • Постоянная панель")
    await interaction.response.send_message(embed=embed, view=MainPanel())

@bot.command(name="panel")
async def panel_prefix(ctx: commands.Context):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        await ctx.send("❌ Команда доступна только в специальном канале.")
        return
    role = ctx.guild.get_role(ALLOWED_ROLE_ID)
    if role is None or role not in ctx.author.roles:
        await ctx.send("❌ У вас нет нужной роли.")
        return
    embed = discord.Embed(
        title="🔧 Панель управления HOFMAN FAMQ",
        description=(
            "Выберите нужное действие ниже 🚩\n\n"
            "🔗 **Инвайт в Hofman FAMQ:** https://discord.gg/uYQuCvdSn9\n"
            f"👑 **Создатель бота:** <@{OWNER_ID}>"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="HOFMAN FAMQ BOT • Постоянная панель")
    await ctx.send(embed=embed, view=MainPanel())

@bot.tree.command(name="setup_tickets", description="Отправить кнопку для создания тикетов в указанный канал")
@app_commands.default_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    channel = bot.get_channel(TICKET_CREATE_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message("❌ Канал для создания тикетов не найден. Проверьте ID.", ephemeral=True)
        return
    embed = discord.Embed(
        title="🎫 Система тикетов",
        description="Нажмите кнопку ниже, чтобы создать тикет. Администраторы ответят вам в личном канале.",
        color=discord.Color.blue()
    )
    view = TicketCreateView()
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"✅ Сообщение с кнопкой отправлено в {channel.mention}", ephemeral=True)
    await log_action(interaction.guild, "Настройка тикетов", interaction.user, f"Канал: {channel.mention}", category="админ")

@bot.tree.command(name="restart", description="Перезагрузить бота (только для владельца)")
async def restart(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ Только владелец бота может перезагружать его.", ephemeral=True)
        return
    await interaction.response.send_message("🔄 Перезагрузка бота...", ephemeral=True)
    await log_action(interaction.guild, "Перезагрузка бота", interaction.user, "По команде /restart", category="админ")
    await bot.close()
    os.execv(sys.executable, [sys.executable] + sys.argv)

# ---------- ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК ----------
@bot.event
async def on_error(event, *args, **kwargs):
    error = sys.exc_info()
    guild = bot.guilds[0] if bot.guilds else None
    await log_action(
        guild,
        f"Ошибка в событии {event}",
        None,
        f"Ошибка: {error[1]}",
        category="ошибка"
    )
    logger.error(f"Ошибка в событии {event}: {error[1]}")

# ---------- ЗАПУСК ----------
@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен!")
    try:
        await bot.change_presence(activity=discord.Game(name="Hofman FAMQ | /panel"))
    except Exception as e:
        print(f"⚠️ Не удалось установить статус: {e}")

    bot.add_view(MainPanel())
    bot.add_view(EventView())
    bot.add_view(TicketCreateView())
    bot.add_view(TicketView())

    try:
        synced = await bot.tree.sync()
        print(f"🔄 Синхронизировано команд: {len(synced)}")
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")

    guild = bot.guilds[0] if bot.guilds else None
    if guild:
        await log_action(guild, "Запуск бота", None, "Бот запущен и готов к работе", category="система")

bot.run(BOT_TOKEN)