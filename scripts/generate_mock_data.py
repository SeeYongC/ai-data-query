"""Generate mock e-commerce dataset for DataAgent demo."""
import sqlite3, random, os
from datetime import date, timedelta

random.seed(42)
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "ecommerce.db")

CATEGORIES = {
    "电子产品": 800, "服装鞋帽": 200, "食品饮料": 30,
    "家居用品": 150, "美妆个护": 100, "运动户外": 300,
}

SUBS = {
    "电子产品": ["手机","电脑","平板","耳机","智能手表"],
    "服装鞋帽": ["男装","女装","童装","鞋子","配饰"],
    "食品饮料": ["零食","饮料","乳制品","调味品","方便食品"],
    "家居用品": ["厨具","家纺","收纳","灯具","装饰"],
    "美妆个护": ["护肤","彩妆","香水","洗护","口腔护理"],
    "运动户外": ["健身器材","户外装备","运动服饰","球类","骑行"],
}

BRANDS = {
    "手机": ["Apple iPhone","Huawei Mate","Xiaomi","OPPO Find","vivo","Samsung Galaxy"],
    "电脑": ["MacBook","ThinkPad","Huawei MateBook","Dell XPS","ROG","Lenovo XiaoXin"],
    "平板": ["iPad","Huawei MatePad","Xiaomi Pad","OPPO Pad","Samsung Galaxy Tab"],
    "耳机": ["AirPods","Huawei FreeBuds","Xiaomi Buds","Sony WH","Bose QC"],
    "智能手表": ["Apple Watch","Huawei Watch","Xiaomi Band","OPPO Watch","Samsung Galaxy Watch"],
    "男装": ["HLA","Uniqlo","ZARA","H&M","Peacebird"],
    "女装": ["ONLY","VERO MODA","Uniqlo","ZARA","Eifini"],
    "童装": ["Balabala","Annil","Mini Peace","GAP Kids","Uniqlo"],
    "鞋子": ["Nike","Adidas","ANTA","Li-Ning","New Balance","Skechers"],
    "配饰": ["Ray-Ban","Pandora","APM Monaco","Swarovski","Casio"],
    "零食": ["Three Squirrels","Bestore","Be & Cheery","Lyfen","Qia Qia"],
    "饮料": ["Coca-Cola","Nongfu Spring","Genki Forest","Luckin","Heytea"],
    "乳制品": ["Mengniu","Yili","Bright","Renyang","Jian Ai"],
    "调味品": ["Haitian","Lee Kum Kee","Totole","Lao Gan Ma","Qianhe"],
    "方便食品": ["Master Kong","Uni-President","Zihai Guo","AirMeter","Ramen Talk"],
    "厨具": ["Supor","ASD","Zwilling","WMF","Carote"],
    "家纺": ["Shuixing","Luolai","Fuanna","Mengjie","Yanxuan"],
    "收纳": ["IKEA","Muji","Taili","Citylong","Storage Doctor"],
    "灯具": ["Opple","NVC","Philips","Panasonic","Xiaomi"],
    "装饰": ["Nordic Nation","British Museum","Palace Museum","Beast","Mumu"],
    "护肤": ["Lancome","Estee Lauder","Proya","Winona","SK-II"],
    "彩妆": ["Perfect Diary","Florasis","MAC","YSL","3CE"],
    "香水": ["Jo Malone","Diptyque","Byredo","To Summer","Scent Library"],
    "洗护": ["Pantene","Head & Shoulders","Schwarzkopf","Bee & Flower","Kerastase"],
    "口腔护理": ["Philips","Oral-B","usmile","Shuke","Marvis"],
    "健身器材": ["Keep","Merach","Yijian","Sole","Matrix"],
    "户外装备": ["Toread","Camel","The North Face","Arc'teryx","Decathlon"],
    "运动服饰": ["Nike","Adidas","Lululemon","Under Armour","ANTA"],
    "球类": ["Wilson","Spalding","Yonex","Li-Ning","DHS"],
    "骑行": ["Giant","Merida","XDS","Dahon","Phoenix"],
}

CITIES = ["北京","上海","广州","深圳","杭州","成都","武汉","南京"]
CITY_W = [0.20,0.20,0.15,0.15,0.10,0.08,0.06,0.06]
AGES = ["18-24","25-34","35-44","45-54","55+"]
AGE_W = [0.15,0.35,0.25,0.15,0.10]
GENDERS = ["男","女"]
GENDER_W = [0.48,0.52]
PAYMENTS = ["微信支付","支付宝","银行卡","货到付款"]
PAY_W = [0.45,0.35,0.15,0.05]
STATUSES = ["completed","cancelled","refunded"]
STAT_W = [0.85,0.05,0.10]
MODELS = ["Pro","Max","Plus","Lite","X","S","SE",""]
MONTHLY_MULT = {1:0.7,2:0.5,3:0.8,4:0.9,5:1.0,6:1.4,7:1.0,8:0.9,9:0.9,10:1.0,11:1.8,12:1.6}


def generate():
    os.makedirs(DB_DIR, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE categories (category_id INTEGER PRIMARY KEY, category_name TEXT NOT NULL, parent_category_id INTEGER, created_at DATE DEFAULT '2024-01-01');
        CREATE TABLE products (product_id INTEGER PRIMARY KEY, product_name TEXT NOT NULL, category_id INTEGER REFERENCES categories(category_id), subcategory TEXT NOT NULL, price REAL NOT NULL, cost REAL NOT NULL, stock_quantity INTEGER DEFAULT 100, created_at DATE DEFAULT '2024-01-01');
        CREATE TABLE users (user_id INTEGER PRIMARY KEY, city TEXT NOT NULL, age_group TEXT NOT NULL, gender TEXT DEFAULT '未知', registered_at DATE NOT NULL);
        CREATE TABLE orders (order_id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(user_id), order_date DATE NOT NULL, total_amount REAL NOT NULL, status TEXT DEFAULT 'completed', payment_method TEXT NOT NULL);
        CREATE TABLE order_items (order_item_id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders(order_id), product_id INTEGER REFERENCES products(product_id), quantity INTEGER DEFAULT 1, unit_price REAL NOT NULL);
    """)

    # Categories
    for i, name in enumerate(CATEGORIES, 1):
        cur.execute("INSERT INTO categories VALUES (?,?,NULL,'2024-01-01')", (i, name))

    # Products
    products, pid = [], 0
    for cat_name, avg_price in CATEGORIES.items():
        cat_id = list(CATEGORIES.keys()).index(cat_name) + 1
        for sub in SUBS[cat_name]:
            for _ in range(6):
                price = round(random.uniform(avg_price * 0.3, avg_price * 2.5), 2)
                cost = round(price * random.uniform(0.35, 0.65), 2)
                brands = BRANDS.get(sub, ["Generic"])
                name = f"{random.choice(brands)} {random.choice(MODELS)} {pid+1}".strip()
                products.append((pid+1, name, cat_id, sub, price, cost))
                pid += 1

    cur.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,100,'2024-01-01')", products)

    # Users
    users = []
    for uid in range(1, 1001):
        reg = date(2023,1,1) + timedelta(days=random.randint(0,1095))
        users.append((uid,
            random.choices(CITIES, weights=CITY_W, k=1)[0],
            random.choices(AGES, weights=AGE_W, k=1)[0],
            random.choices(GENDERS, weights=GENDER_W, k=1)[0],
            reg.isoformat()))
    cur.executemany("INSERT INTO users VALUES (?,?,?,?,?)", users)

    # Orders
    orders, order_items = [], []
    oid, oiid = 1, 1
    current = date(2025,1,1)
    while current <= date(2026,6,30):
        mult = MONTHLY_MULT.get(current.month, 1.0)
        if current.weekday() >= 5: mult *= 1.3
        daily = max(1, int(random.gauss(18 * mult, 5)))
        for _ in range(daily):
            uid = random.randint(1, 1000)
            n_items = random.choices([1,2,3,4,5], weights=[0.25,0.35,0.25,0.1,0.05], k=1)[0]
            pool = random.sample([p[0] for p in products], min(15, len(products)))
            selected = random.sample(pool, min(n_items, len(pool)))
            total = 0.0
            for spid in selected:
                qty = random.choices([1,2,3], weights=[0.7,0.2,0.1], k=1)[0]
                uprice = products[spid - 1][4]
                order_items.append((oiid, oid, spid, qty, uprice))
                total += uprice * qty
                oiid += 1
            total = round(total, 2)
            st = random.choices(STATUSES, weights=STAT_W, k=1)[0]
            pm = random.choices(PAYMENTS, weights=PAY_W, k=1)[0]
            orders.append((oid, uid, current.isoformat(), total, st, pm))
            oid += 1
        current += timedelta(days=1)

    for i in range(0, len(orders), 500):
        cur.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", orders[i:i+500])
    for i in range(0, len(order_items), 1000):
        cur.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", order_items[i:i+1000])

    cur.executescript("""
        CREATE INDEX idx_orders_date ON orders(order_date);
        CREATE INDEX idx_orders_user ON orders(user_id);
        CREATE INDEX idx_orders_status ON orders(status);
        CREATE INDEX idx_order_items_order ON order_items(order_id);
        CREATE INDEX idx_order_items_product ON order_items(product_id);
        CREATE INDEX idx_products_category ON products(category_id);
    """)

    conn.commit()
    conn.close()

    print(f"Database: {DB_PATH}")
    print(f"  Products: {len(products)} | Users: 1000 | Orders: {len(orders)} | Items: {len(order_items)}")
    print("\nSample queries:")
    for q in ["上月销售额最高的五个品类？","北京和上海用户的客单价对比","今年各月销售额趋势","哪个年龄段用户消费能力最强？","退货率最高的三个品类","各支付方式的使用占比"]:
        print(f'  "{q}"')

if __name__ == "__main__":
    generate()
