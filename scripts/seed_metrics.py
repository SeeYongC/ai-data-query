"""Seed metric definitions into the database for governance module."""
import sqlite3, os
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ecommerce.db")
METRICS = [
    ("active_users", "活跃用户", "财务口径", "财务部", "orders", "u.user_id IN (SELECT DISTINCT user_id FROM orders WHERE status='completed' AND order_date >= date('now','-30 days'))", "统计时有交易的独立用户数", "近30天内有已完成交易行为的用户", ""),
    ("active_users", "活跃用户", "运营口径", "运营部", "user_logins", "u.user_id IN (SELECT DISTINCT user_id FROM user_logins WHERE login_date >= date('now','-7 days'))", "需要接入用户登录日志表 user_logins", "近7天内有登录行为的用户", "当前模拟库无此表"),
    ("active_users", "活跃用户", "市场口径", "市场部", "user_clicks", "u.user_id IN (SELECT DISTINCT user_id FROM user_clicks WHERE click_date >= date('now','-90 days'))", "需要接入用户点击日志表 user_clicks", "近90天内有页面点击行为的用户", "当前模拟库无此表"),
    ("sales_revenue", "销售额", "财务口径", "财务部", "orders", "o.status = 'completed'", "已完成的订单总额", "已确认收货且未退款的订单金额", ""),
    ("sales_revenue", "销售额", "运营口径", "运营部", "orders", "o.status IN ('completed','pending')", "含未付款的订单总额", "下单金额，不含退款", ""),
    ("gross_margin", "毛利率", "财务口径", "财务部", "orders, order_items, products", "(SUM(oi.quantity * oi.unit_price) - SUM(oi.quantity * p.cost)) / SUM(oi.quantity * oi.unit_price) * 100", "不含营销费用", "(收入-成本)/收入", ""),
    ("gross_margin", "毛利率", "运营口径", "运营部", "orders, order_items, products", "(SUM(oi.quantity * oi.unit_price) - SUM(oi.quantity * p.cost) - SUM(ms.spend)) / SUM(oi.quantity * oi.unit_price) * 100", "含营销费用", "(收入-成本-费用)/收入", ""),
    ("avg_order_value", "客单价", "严格口径", "财务部", "orders", "SUM(o.total_amount) / COUNT(DISTINCT o.order_id)", "已完成订单的客单价", "总销售额/总订单数", ""),
    ("avg_order_value", "客单价", "宽口径", "运营部", "orders", "SUM(o.total_amount) / COUNT(DISTINCT o.user_id)", "人均消费额", "总销售额/购买用户数", ""),
    ("repurchase_rate", "复购率", "月度口径", "运营部", "orders", "COUNT(DISTINCT CASE WHEN order_count >= 2 THEN user_id END) * 100.0 / COUNT(DISTINCT user_id)", "当月购买2次用户占比", "购买2次用户/总购买用户", "需按月分组"),
    ("refund_rate", "退款率", "订单口径", "运营部", "orders", "COUNT(CASE WHEN o.status='refunded' THEN 1 END) * 100.0 / COUNT(*)", "退款订单数/总订单数", "按订单数计算", ""),
    ("refund_rate", "退款率", "金额口径", "财务部", "orders", "SUM(CASE WHEN o.status='refunded' THEN o.total_amount ELSE 0 END) * 100.0 / SUM(o.total_amount)", "退款金额/总金额", "按金额计算", ""),
    ("conversion_rate", "转化率", "下单-支付", "财务部", "orders", "COUNT(CASE WHEN o.status='completed' THEN 1 END) * 100.0 / COUNT(*)", "支付订单/下单订单", "下单后完成支付的比例", ""),
    ("new_users", "新用户", "注册口径", "运营部", "users", "u.registered_at >= date('now','-30 days')", "近30天注册的用户", "按注册时间定义", ""),
    ("new_users", "新用户", "首单口径", "运营部", "orders", "u.user_id IN (SELECT user_id FROM orders WHERE status='completed' GROUP BY user_id HAVING MIN(order_date) >= date('now','-30 days'))", "近30天首次下单的用户", "按首次下单时间定义", ""),
    ("user_retention", "留存率", "次日留存", "运营部", "orders", "用户首次购买后次日再次购买的比例", "", "用户在首次购买后第二天仍有购买行为的比例", "需自关联 orders 表"),
    ("user_retention", "留存率", "7日留存", "运营部", "orders", "用户首次购买后7日内再次购买的比例", "", "用户在首次购买后7天内仍有购买行为的比例", ""),
]
def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript("""CREATE TABLE IF NOT EXISTS metric_definitions (definition_id INTEGER PRIMARY KEY AUTOINCREMENT, metric_key TEXT NOT NULL, metric_name TEXT NOT NULL, definition_name TEXT NOT NULL, owner_department TEXT, data_source TEXT, sql_condition TEXT NOT NULL, sql_notes TEXT, description TEXT NOT NULL, business_rules TEXT, is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now')));CREATE TABLE IF NOT EXISTS user_metric_preferences (preference_id INTEGER PRIMARY KEY AUTOINCREMENT, user_identifier TEXT NOT NULL, metric_key TEXT NOT NULL, definition_id INTEGER NOT NULL, last_used_at TEXT DEFAULT (datetime('now')), UNIQUE(user_identifier, metric_key));CREATE INDEX IF NOT EXISTS idx_metric_defs_key ON metric_definitions(metric_key);CREATE INDEX IF NOT EXISTS idx_metric_prefs_user ON user_metric_preferences(user_identifier);""")
    cur.execute("DELETE FROM metric_definitions")
    cur.execute("DELETE FROM user_metric_preferences")
    cur.executemany("INSERT INTO metric_definitions (metric_key, metric_name, definition_name, owner_department, data_source, sql_condition, sql_notes, description, business_rules) VALUES (?,?,?,?,?,?,?,?,?)", METRICS)
    conn.commit()
    cur.execute("SELECT metric_name, COUNT(*) FROM metric_definitions GROUP BY metric_name ORDER BY metric_name")
    print("Metrics seeded:")
    for name, count in cur.fetchall():
        cur.execute("SELECT definition_name FROM metric_definitions WHERE metric_name=? ORDER BY definition_id", (name,))
        defs = [r[0] for r in cur.fetchall()]
        print(f"  {name}: {count} definitions: {', '.join(defs)}")
    conn.close()
    print(f"\nTotal: {len(METRICS)} definitions across {len(set(m[0] for m in METRICS))} metrics")
if __name__ == "__main__":
    seed()
