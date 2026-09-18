import sqlite3
from typing import Optional
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="#", intents=intents)

DB_NAME = "sattim_auto.db"


def execute_query(query: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False, commit: bool = False):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    
    data = None
    if fetchone:
        data = cursor.fetchone()
    elif fetchall:
        data = cursor.fetchall()
        
    if commit:
        conn.commit()
        data = cursor.lastrowid
        
    conn.close()
    return data


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            discord_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id TEXT NOT NULL,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            price TEXT NOT NULL,
            description TEXT NOT NULL,
            image_url TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_id INTEGER NOT NULL,
            buyer_id TEXT NOT NULL,
            offer_amount TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


SATTIM_LINES = {
    "welcome": "Türkiye'nin Lider Araç Pazarı **sattım.com**'a hoş geldiniz!",
    "not_registered": "⚠️ Önce `#uye Ad Soyad` şeklinde üye olmanız gerekmektedir.",
    "ad_success": "✅ İlanınız **sattım.com** vitrininde başarıyla yayınlandı! İyi satışlar dileriz.",
    "offer_success": "📩 Teklifiniz araç sahibine özel mesaj olarak başarıyla iletildi!",
    "no_ads": "🚘 Şu anda **sattım.com** üzerinde aktif araç ilanı bulunmamaktadır."
}


# --- PAZARLIK & KARŞI TEKLİF NESNELERİ ---

class CounterOfferModal(discord.ui.Modal, title="🤝 Karşı Teklif / Pazarlık Yap"):
    def __init__(self, ad_id: int, buyer_id: str, channel_id: int):
        super().__init__()
        self.ad_id = ad_id
        self.buyer_id = buyer_id
        self.channel_id = channel_id

    counter_price = discord.ui.TextInput(
        label="Son Oluru / Karşı Fiyatınız (TL)",
        placeholder="Örn: 675.000",
        required=True,
        max_length=30
    )

    async def on_submit(self, interaction: discord.Interaction):
        ad = execute_query("SELECT brand, model FROM ads WHERE id = ?", (self.ad_id,), fetchone=True)
        brand_model = f"{ad[0]} {ad[1]}" if ad else "Araç"

        try:
            buyer = await interaction.client.fetch_user(int(self.buyer_id))
            embed = discord.Embed(
                title="🔄 Satıcıdan Karşı Teklif Geldi!",
                description=f"**#{self.ad_id}** numaralı ilan için satıcı bir karşı teklifte bulundu.",
                color=discord.Color.orange()
            )
            embed.add_field(name="🚗 Araç", value=brand_model, inline=False)
            embed.add_field(name="👤 Satıcı", value=f"{interaction.user.mention}", inline=True)
            embed.add_field(name="💰 Satıcının Son Oluru", value=f"**{self.counter_price.value} TL**", inline=True)
            embed.set_footer(text="sattım.com • Pazarlık Masası")

            view = BuyerAcceptCounterView(
                ad_id=self.ad_id,
                seller_id=str(interaction.user.id),
                final_amount=self.counter_price.value,
                channel_id=self.channel_id
            )
            await buyer.send(embed=embed, view=view)
            await interaction.response.send_message(
                f"✅ **{self.counter_price.value} TL** tutarındaki karşı teklifiniz alıcıya iletildi!",
                ephemeral=True
            )
        except Exception:
            await interaction.response.send_message("❌ Alıcıya özel mesaj gönderilemedi.", ephemeral=True)


class BuyerAcceptCounterView(discord.ui.View):
    """Alıcının satıcıdan gelen karşı teklifi kabul etmesi veya reddetmesi için view"""
    def __init__(self, ad_id: int, seller_id: str, final_amount: str, channel_id: int):
        super().__init__(timeout=None)
        self.ad_id = ad_id
        self.seller_id = seller_id
        self.final_amount = final_amount
        self.channel_id = channel_id

    @discord.ui.button(label="✅ Karşı Teklifi Kabul Et", style=discord.ButtonStyle.success)
    async def accept_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="✅ **Pazarlığı kabul ettiniz! Satış duyurusu kanala iletiliyor.**", view=self)

        ad = execute_query("SELECT brand, model FROM ads WHERE id = ?", (self.ad_id,), fetchone=True)
        brand_model = f"{ad[0]} {ad[1]}" if ad else "Araç"

        channel = interaction.client.get_channel(self.channel_id)
        if channel:
            embed = discord.Embed(
                title="🎉 SATIŞ GERÇEKLEŞTİ! #sattim",
                description=f"**#{self.ad_id}** numaralı ilan için pazarlık anlaşmayla sonuçlandı!",
                color=discord.Color.gold()
            )
            embed.add_field(name="🚗 Araç", value=brand_model, inline=True)
            embed.add_field(name="👤 Satıcı", value=f"<@{self.seller_id}>", inline=True)
            embed.add_field(name="🤝 Alan Kişi", value=f"<@{interaction.user.id}>", inline=True)
            embed.add_field(name="💰 Anlaşılan Fiyat", value=f"**{self.final_amount} TL**", inline=False)
            embed.set_footer(text="sattım.com • Hayırlı Olsun!")

            await channel.send(content="#sattim", embed=embed)

    @discord.ui.button(label="❌ Reddet", style=discord.ButtonStyle.danger)
    async def reject_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="❌ Karşı teklifi reddettiniz.", view=self)


class AcceptOfferView(discord.ui.View):
    """Satıcının alıcıdan gelen ilk teklifi yönettiği view"""
    def __init__(self, ad_id: int, buyer_id: str, offer_amount: str, channel_id: int):
        super().__init__(timeout=None)
        self.ad_id = ad_id
        self.buyer_id = buyer_id
        self.offer_amount = offer_amount
        self.channel_id = channel_id

    @discord.ui.button(label="✅ Teklifi Kabul Et", style=discord.ButtonStyle.success)
    async def accept_offer(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="✅ **Teklifi kabul ettiniz! Satış duyurusu kanala iletildi.**", view=self)

        ad = execute_query("SELECT brand, model FROM ads WHERE id = ?", (self.ad_id,), fetchone=True)
        brand_model = f"{ad[0]} {ad[1]}" if ad else "Araç"

        channel = interaction.client.get_channel(self.channel_id)
        if channel:
            embed = discord.Embed(
                title="🎉 SATIŞ GERÇEKLEŞTİ! #sattim",
                description=f"**#{self.ad_id}** numaralı ilan için verilen teklif satıcı tarafından onaylandı!",
                color=discord.Color.gold()
            )
            embed.add_field(name="🚗 Araç", value=brand_model, inline=True)
            embed.add_field(name="👤 Satıcı", value=f"<@{interaction.user.id}>", inline=True)
            embed.add_field(name="🤝 Alan Kişi", value=f"<@{self.buyer_id}>", inline=True)
            embed.add_field(name="💰 Satış Fiyatı", value=f"**{self.offer_amount} TL**", inline=False)
            embed.set_footer(text="sattım.com • Hayırlı Olsun!")

            await channel.send(content="#sattim", embed=embed)

    @discord.ui.button(label="🔄 Karşı Teklif Yap", style=discord.ButtonStyle.primary)
    async def counter_offer(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CounterOfferModal(ad_id=self.ad_id, buyer_id=self.buyer_id, channel_id=self.channel_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="❌ Reddet", style=discord.ButtonStyle.danger)
    async def reject_offer(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="❌ Teklif reddedildi.", view=self)


# --- DIĞER MODALLAR VE VIEW'LAR ---

class PostAdModal(discord.ui.Modal, title="🚗 sattım.com - Yeni İlan Oluştur"):
    brand = discord.ui.TextInput(label="Marka", placeholder="Örn: BMW, Audi, Mercedes", required=True, max_length=50)
    model = discord.ui.TextInput(label="Model / Yıl", placeholder="Örn: 320i - 2021", required=True, max_length=50)
    price = discord.ui.TextInput(label="Fiyat (TL)", placeholder="Örn: 1.450.000", required=True, max_length=30)
    description = discord.ui.TextInput(
        label="Araç Açıklaması",
        style=discord.TextStyle.paragraph,
        placeholder="Aracın ekspertiz, km ve genel durum bilgilerini giriniz...",
        required=True,
        max_length=1000
    )
    image_url = discord.ui.TextInput(
        label="Görsel Bağlantısı (URL)",
        placeholder="https://i.imgur.com/... veya https://...",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        ad_id = execute_query(
            "INSERT INTO ads (seller_id, brand, model, price, description, image_url) VALUES (?, ?, ?, ?, ?, ?)",
            (str(interaction.user.id), self.brand.value, self.model.value, self.price.value, self.description.value, self.image_url.value),
            commit=True
        )

        embed = discord.Embed(
            title=f"📢 YENİ İLAN: {self.brand.value} {self.model.value}",
            description=self.description.value,
            color=discord.Color.blue()
        )
        embed.set_author(name="sattım.com Oto Vitrini", icon_url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None)
        embed.add_field(name="💰 Fiyat", value=f"**{self.price.value} TL**", inline=True)
        embed.add_field(name="👤 Satıcı", value=interaction.user.mention, inline=True)
        embed.add_field(name="🆔 İlan No", value=f"`#{ad_id}`", inline=True)
        embed.set_image(url=self.image_url.value)
        embed.set_footer(text="sattım.com • Güvenli Araç Alım Satımı")

        view = OfferView(ad_id=ad_id)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(SATTIM_LINES["ad_success"], ephemeral=True)


class OfferModal(discord.ui.Modal, title="💰 sattım.com - Teklif Ver"):
    def __init__(self, ad_id: int):
        super().__init__()
        self.ad_id = ad_id

    offer_amount = discord.ui.TextInput(
        label="Teklif Ettiğiniz Tutar (TL)",
        placeholder="Örn: 1.400.000",
        required=True,
        max_length=30
    )

    async def on_submit(self, interaction: discord.Interaction):
        execute_query(
            "INSERT INTO offers (ad_id, buyer_id, offer_amount) VALUES (?, ?, ?)",
            (self.ad_id, str(interaction.user.id), self.offer_amount.value),
            commit=True
        )

        ad = execute_query("SELECT seller_id, brand, model FROM ads WHERE id = ?", (self.ad_id,), fetchone=True)

        if ad:
            seller_id, brand, model = ad
            try:
                seller = await interaction.client.fetch_user(int(seller_id))
                dm_embed = discord.Embed(
                    title="📩 İlanınıza Yeni Teklif Geldi!",
                    description=f"**sattım.com** üzerindeki **#{self.ad_id}** numaralı ilanınıza teklif yapıldı.",
                    color=discord.Color.green()
                )
                dm_embed.add_field(name="🚗 Araç", value=f"{brand} {model}", inline=False)
                dm_embed.add_field(name="👤 Teklif Veren", value=f"{interaction.user.mention} ({interaction.user})", inline=True)
                dm_embed.add_field(name="💵 Teklif Tutarı", value=f"**{self.offer_amount.value} TL**", inline=True)
                dm_embed.set_footer(text="sattım.com Bilgilendirme Servisi")

                accept_view = AcceptOfferView(
                    ad_id=self.ad_id,
                    buyer_id=str(interaction.user.id),
                    offer_amount=self.offer_amount.value,
                    channel_id=interaction.channel_id
                )
                await seller.send(embed=dm_embed, view=accept_view)
            except Exception:
                pass

        await interaction.response.send_message(SATTIM_LINES["offer_success"], ephemeral=True)


class OfferView(discord.ui.View):
    def __init__(self, ad_id: int):
        super().__init__(timeout=None)
        self.ad_id = ad_id

    @discord.ui.button(label="🤝 Teklif Ver", style=discord.ButtonStyle.success, custom_id="btn_sattim_offer")
    async def offer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = execute_query("SELECT * FROM users WHERE discord_id = ?", (str(interaction.user.id),), fetchone=True)

        if not user:
            return await interaction.response.send_message(SATTIM_LINES["not_registered"], ephemeral=True)

        await interaction.response.send_modal(OfferModal(ad_id=self.ad_id))


class AdSelectMenu(discord.ui.Select):
    def __init__(self, ads):
        options = [
            discord.SelectOption(
                label=f"#{ad[0]} - {ad[2]} {ad[3]}",
                description=f"Fiyat: {ad[4]} TL",
                value=str(ad[0]),
                emoji="🚗"
            ) for ad in ads
        ]
        super().__init__(placeholder="İncelemek istediğiniz aracı seçiniz...", options=options)

    async def callback(self, interaction: discord.Interaction):
        ad_id = int(self.values[0])
        ad = execute_query("SELECT * FROM ads WHERE id = ?", (ad_id,), fetchone=True)

        if not ad:
            return await interaction.response.send_message("❌ Bu ilan bulunamadı veya yayından kaldırılmış.", ephemeral=True)

        embed = discord.Embed(
            title=f"🚗 {ad[2]} {ad[3]}",
            description=ad[5],
            color=discord.Color.blue()
        )
        embed.set_author(name="sattım.com Araç Detayı")
        embed.add_field(name="💰 Fiyat", value=f"**{ad[4]} TL**", inline=True)
        embed.add_field(name="👤 Satıcı", value=f"<@{ad[1]}>", inline=True)
        embed.add_field(name="🆔 İlan Kodu", value=f"`#{ad[0]}`", inline=True)
        embed.set_image(url=ad[6])
        embed.set_footer(text="sattım.com • İlan Detay Görünümü")

        view = OfferView(ad_id=ad[0])
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class GarageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🚗 İlan Ver", style=discord.ButtonStyle.success, emoji="➕")
    async def post_ad(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = execute_query("SELECT * FROM users WHERE discord_id = ?", (str(interaction.user.id),), fetchone=True)
        if not user:
            return await interaction.response.send_message(SATTIM_LINES["not_registered"], ephemeral=True)

        await interaction.response.send_modal(PostAdModal())

    @discord.ui.button(label="📜 Vitrini İncele", style=discord.ButtonStyle.primary, emoji="🔍")
    async def list_ads(self, interaction: discord.Interaction, button: discord.ui.Button):
        ads = execute_query("SELECT * FROM ads ORDER BY id DESC LIMIT 25", fetchall=True)

        if not ads:
            return await interaction.response.send_message(SATTIM_LINES["no_ads"], ephemeral=True)

        view = discord.ui.View()
        view.add_item(AdSelectMenu(ads))
        await interaction.response.send_message("🚘 **sattım.com** Vitrinindeki Son İlanlar:", view=view, ephemeral=True)

    @discord.ui.button(label="📊 Pazar İstatistikleri", style=discord.ButtonStyle.secondary, emoji="📈")
    async def stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        ad_count = execute_query("SELECT COUNT(*) FROM ads", fetchone=True)[0]
        user_count = execute_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
        offer_count = execute_query("SELECT COUNT(*) FROM offers", fetchone=True)[0]

        embed = discord.Embed(title="📊 sattım.com Platform İstatistikleri", color=discord.Color.dark_theme())
        embed.add_field(name="🚗 Toplam İlan", value=f"**{ad_count}** adet", inline=True)
        embed.add_field(name="👥 Kayıtlı Üye", value=f"**{user_count}** kişi", inline=True)
        embed.add_field(name="🤝 Yapılan Teklifler", value=f"**{offer_count}** adet", inline=True)
        embed.add_field(name="⚡ Durum", value="`7/24 Aktif Hizmet`", inline=False)
        embed.set_footer(text="sattım.com • Güvenli Otomobil Pazarı")

        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.event
async def on_ready():
    init_db()
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, 
            name="sattım.com | #ilan"
        )
    )
    print(f"✅ {bot.user.name} online! sattım.com veritabanı başarıyla bağlandı.")


@bot.command(name="uye")
async def register(ctx, *, full_name: Optional[str] = None):
    if not full_name:
        return await ctx.reply("⚠️ Lütfen adınızı ve soyadınızı belirtin. Kullanım: `#uye Ad Soyad`")

    execute_query(
        "INSERT OR REPLACE INTO users (discord_id, full_name) VALUES (?, ?)",
        (str(ctx.author.id), full_name),
        commit=True
    )

    embed = discord.Embed(
        title="✅ Kayıt Başarılı",
        description=f"Hoş geldiniz **{full_name}**! **sattım.com** platformuna kaydınız tamamlandı.",
        color=discord.Color.green()
    )
    embed.add_field(name="💡 İpucu", value="`#ilan` yazarak araç vitrinini açabilir ve ilan verebilirsiniz.", inline=False)
    await ctx.reply(embed=embed)


@bot.command(name="ilan")
async def garage(ctx):
    embed = discord.Embed(
        title="🏎️ sattım.com Oto Pazarı",
        description=f"{SATTIM_LINES['welcome']}\n\nAşağıdaki butonları kullanarak hemen ilan verebilir, vitrindeki araçları inceleyebilir ve istatistikleri görebilirsiniz.",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/3202/3202003.png")
    embed.set_footer(text="sattım.com • Türkiye'nin Dijital Otomobil Pazarı")
    
    await ctx.send(embed=embed, view=GarageView())


@bot.command(name="yardim")
async def help_command(ctx):
    embed = discord.Embed(title="❓ sattım.com Bot Komutları", color=discord.Color.blue())
    embed.add_field(name="#uye Ad Soyad", value="Platforma kayıt olmanızı sağlar.", inline=False)
    embed.add_field(name="#ilan", value="sattım.com panelini açar (İlan ekle, Vitrin incele, İstatistikler).", inline=False)
    embed.add_field(name="#yardim", value="Bu yardım menüsünü görüntüler.", inline=False)
    await ctx.reply(embed=embed)

bot.run("")