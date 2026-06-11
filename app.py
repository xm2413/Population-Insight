from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from flask import Flask, Response, flash, g, redirect, render_template_string, request, session, url_for

from population_trend.analysis_service import (
    build_bars,
    build_line_points,
    dashboard_summary,
    get_global_continents,
    get_alerts,
    global_population_summary,
    latest_records,
    linear_forecast,
    region_statistics,
)
from population_trend.auth import admin_required, authenticate, current_user, log_action, login_required
from population_trend.config import METRIC_LABELS
from population_trend.database import close_db, init_database, query_all
from population_trend.record_service import (
    add_region,
    create_record,
    delete_record_by_id,
    get_record,
    get_regions,
    get_years,
    import_csv_text,
    list_records,
    parse_record_form,
    records_to_csv,
    update_record,
)
from population_trend.visualization_service import generate_charts


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("POP_TREND_SECRET", "dev-secret-change-me")
app.teardown_appcontext(close_db)


@app.before_request
def load_user() -> None:
    g.user = current_user()


@app.context_processor
def inject_context() -> dict:
    return {"current_user": g.user, "metric_labels": METRIC_LABELS, "now_year": datetime.now().year}


BASE_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }} - 人口趋势与分析管理系统</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='app.css') }}">
</head>
<body>
{% if current_user %}
<aside class="sidebar">
  <div class="brand"><span class="brand-mark">人</span><div><strong>人口趋势分析</strong><small>Population Trend</small></div></div>
  <nav>
    <a href="{{ url_for('dashboard') }}" class="{{ 'active' if active == 'dashboard' else '' }}">概览</a>
    <a href="{{ url_for('records') }}" class="{{ 'active' if active == 'records' else '' }}">人口数据</a>
    <a href="{{ url_for('analytics') }}" class="{{ 'active' if active == 'analytics' else '' }}">统计分析</a>
    <a href="{{ url_for('global_population') }}" class="{{ 'active' if active == 'global' else '' }}">全球统计</a>
    <a href="{{ url_for('comparison') }}" class="{{ 'active' if active == 'comparison' else '' }}">地区对比</a>
    <a href="{{ url_for('forecast') }}" class="{{ 'active' if active == 'forecast' else '' }}">趋势预测</a>
    <a href="{{ url_for('charts') }}" class="{{ 'active' if active == 'charts' else '' }}">可视化</a>
    <a href="{{ url_for('alerts') }}" class="{{ 'active' if active == 'alerts' else '' }}">风险预警</a>
    <a href="{{ url_for('import_data') }}" class="{{ 'active' if active == 'import' else '' }}">数据导入</a>
    <a href="{{ url_for('regions') }}" class="{{ 'active' if active == 'regions' else '' }}">地区档案</a>
    <a href="{{ url_for('logs') }}" class="{{ 'active' if active == 'logs' else '' }}">操作日志</a>
  </nav>
</aside>
{% endif %}
<main class="{{ 'shell' if current_user else 'login-shell' }}">
  {% if current_user %}
  <header class="topbar">
    <div><h1>{{ title }}</h1><p>{{ subtitle }}</p></div>
    <div class="user-pill"><span>{{ current_user['username'] }} · {{ '管理员' if current_user['role'] == 'admin' else '查看者' }}</span><a href="{{ url_for('logout') }}">退出</a></div>
  </header>
  {% endif %}
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}<section class="messages">{% for category, message in messages %}<div class="message {{ category }}">{{ message }}</div>{% endfor %}</section>{% endif %}
  {% endwith %}
  {{ body|safe }}
</main>
</body>
</html>
"""


def render_page(title: str, subtitle: str, active: str, body: str, **context) -> str:
    return render_template_string(
        BASE_TEMPLATE,
        title=title,
        subtitle=subtitle,
        active=active,
        body=render_template_string(body, **context),
        **context,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = authenticate(username, request.form.get("password", ""))
        if user:
            session["username"] = username
            flash(f"欢迎回来，{username}。", "success")
            log_action("登录", f"{username} 登录系统")
            return redirect(url_for("dashboard"))
        flash("用户名或密码错误。", "error")
    body = """
    <section class="login-panel">
      <div class="login-copy">
        <span class="eyebrow">课程设计</span>
        <h1>人口趋势与分析管理系统</h1>
        <p>支持人口数据维护、趋势分析、地区对比、预测预警、Matplotlib 可视化与 CSV 导入导出。</p>
        <div class="demo-account">管理员：admin / admin123<br>查看者：viewer / viewer123</div>
      </div>
      <form method="post" class="login-form">
        <label>用户名<input name="username" required autofocus></label>
        <label>密码<input name="password" type="password" required></label>
        <button type="submit">登录系统</button>
      </form>
    </section>
    """
    return render_page("登录", "", "", body)


@app.route("/logout")
def logout():
    session.clear()
    flash("已退出登录。", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    summary = dashboard_summary()
    line = build_line_points(summary["trend_points"])
    bars = build_bars(summary["latest"][:6])
    body = """
    <section class="kpis">
      <article><span>最新年份</span><strong>{{ summary.latest_year or '-' }}</strong></article>
      <article><span>地区数量</span><strong>{{ summary.region_count }}</strong></article>
      <article><span>数据记录</span><strong>{{ summary.record_count }}</strong></article>
      <article><span>最新总人口</span><strong>{{ summary.total_population }}</strong><small>万人</small></article>
      <article><span>平均自然增长率</span><strong>{{ summary.avg_growth }}‰</strong></article>
      <article><span>预警地区</span><strong>{{ summary.high_risk_count }}</strong></article>
    </section>
    <section class="grid two">
      <div class="panel">
        <div class="panel-head"><h2>总体人口趋势</h2><span>{{ line.min }} - {{ line.max }} 万人</span></div>
        <svg class="line-chart" viewBox="0 0 720 280" preserveAspectRatio="none">
          <line x1="0" y1="244" x2="720" y2="244"></line><polyline points="{{ line.polyline }}"></polyline>
          {% for item in line.labels %}<text x="{{ item.x }}" y="270">{{ item.label }}</text>{% endfor %}
        </svg>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>最新年份人口排行</h2><a href="{{ url_for('records') }}">查看全部</a></div>
        <div class="bar-list">{% for bar in bars %}<div class="bar-row"><span>{{ bar.label }}</span><div><i style="width: {{ bar.width }}%"></i></div><strong>{{ bar.value }}</strong></div>{% endfor %}</div>
      </div>
    </section>
    """
    return render_page("概览仪表盘", "展示最新人口规模、增长与风险概况。", "dashboard", body, summary=summary, line=line, bars=bars)


@app.route("/records")
@login_required
def records():
    region = request.args.get("region", "").strip()
    year = request.args.get("year", "").strip()
    keyword = request.args.get("keyword", "").strip()
    rows = list_records(region, year, keyword)
    body = """
    <section class="toolbar">
      <form class="filters" method="get">
        <select name="region"><option value="">全部地区</option>{% for item in regions %}<option value="{{ item }}" {{ 'selected' if item == selected_region else '' }}>{{ item }}</option>{% endfor %}</select>
        <select name="year"><option value="">全部年份</option>{% for item in years %}<option value="{{ item }}" {{ 'selected' if item|string == selected_year else '' }}>{{ item }}</option>{% endfor %}</select>
        <input name="keyword" value="{{ keyword }}" placeholder="搜索来源或备注"><button type="submit">筛选</button>
      </form>
      <div class="actions"><a class="button ghost" href="{{ url_for('export_records', region=selected_region, year=selected_year, keyword=keyword) }}">导出 CSV</a>{% if current_user.role == 'admin' %}<a class="button" href="{{ url_for('new_record') }}">新增数据</a>{% endif %}</div>
    </section>
    <section class="panel table-panel">
      <table>
        <thead><tr><th>地区</th><th>年份</th><th>总人口</th><th>男性</th><th>女性</th><th>出生率</th><th>死亡率</th><th>自然增长率</th><th>老龄化率</th><th>城镇化率</th><th>操作</th></tr></thead>
        <tbody>{% for row in rows %}<tr><td>{{ row.region }}</td><td>{{ row.year }}</td><td>{{ row.total_population }}</td><td>{{ row.male_population }}</td><td>{{ row.female_population }}</td><td>{{ row.birth_rate }}‰</td><td>{{ row.death_rate }}‰</td><td class="{{ 'bad' if row.natural_growth_rate < 0 else 'good' }}">{{ row.natural_growth_rate }}‰</td><td>{{ row.aging_rate }}%</td><td>{{ row.urbanization_rate }}%</td><td class="row-actions"><a href="{{ url_for('edit_record', record_id=row.id) }}">编辑</a>{% if current_user.role == 'admin' %}<form method="post" action="{{ url_for('delete_record', record_id=row.id) }}"><button onclick="return confirm('确定删除这条数据吗？')">删除</button></form>{% endif %}</td></tr>{% else %}<tr><td colspan="11" class="empty">没有符合条件的数据。</td></tr>{% endfor %}</tbody>
      </table>
    </section>
    """
    return render_page("人口数据管理", "查询、维护和导出年度人口指标。", "records", body, rows=rows, regions=get_regions(), years=get_years(), selected_region=region, selected_year=year, keyword=keyword)


RECORD_FORM_TEMPLATE = """
<section class="panel form-panel">
  <form method="post" class="record-form">
    <div class="form-grid">
      <label>地区<input name="region" required value="{{ record.region if record else '' }}"></label>
      <label>年份<input name="year" type="number" min="1900" required value="{{ record.year if record else now_year }}"></label>
      <label>总人口（万人）<input name="total_population" type="number" min="0" required value="{{ record.total_population if record else '' }}"></label>
      <label>男性人口（万人）<input name="male_population" type="number" min="0" required value="{{ record.male_population if record else '' }}"></label>
      <label>女性人口（万人）<input name="female_population" type="number" min="0" required value="{{ record.female_population if record else '' }}"></label>
      <label>出生率（‰）<input name="birth_rate" type="number" step="0.01" min="0" required value="{{ record.birth_rate if record else '' }}"></label>
      <label>死亡率（‰）<input name="death_rate" type="number" step="0.01" min="0" required value="{{ record.death_rate if record else '' }}"></label>
      <label>自然增长率（‰）<input name="natural_growth_rate" type="number" step="0.01" required value="{{ record.natural_growth_rate if record else '' }}"></label>
      <label>老龄化率（%）<input name="aging_rate" type="number" step="0.01" min="0" required value="{{ record.aging_rate if record else '' }}"></label>
      <label>城镇化率（%）<input name="urbanization_rate" type="number" step="0.01" min="0" required value="{{ record.urbanization_rate if record else '' }}"></label>
      <label>数据来源<input name="source" value="{{ record.source if record else '' }}"></label>
      <label>备注<input name="note" value="{{ record.note if record else '' }}"></label>
    </div>
    <div class="form-actions"><a class="button ghost" href="{{ url_for('records') }}">返回</a><button type="submit">保存数据</button></div>
  </form>
</section>
"""


@app.route("/records/new", methods=["GET", "POST"])
@admin_required
def new_record():
    if request.method == "POST":
        try:
            data = parse_record_form(request.form)
            create_record(data)
            log_action("新增人口数据", f"{data['region']} {data['year']}")
            flash("人口数据已新增。", "success")
            return redirect(url_for("records"))
        except (ValueError, sqlite3.IntegrityError) as error:
            flash(f"保存失败：{error}", "error")
    return render_page("新增人口数据", "录入一个地区某一年度的人口指标。", "records", RECORD_FORM_TEMPLATE, record=None)


@app.route("/records/<int:record_id>/edit", methods=["GET", "POST"])
@login_required
def edit_record(record_id: int):
    record = get_record(record_id)
    if record is None:
        flash("数据不存在。", "error")
        return redirect(url_for("records"))
    if request.method == "POST":
        if g.user["role"] != "admin":
            flash("查看者不能修改数据。", "error")
            return redirect(url_for("records"))
        try:
            data = parse_record_form(request.form)
            update_record(record_id, data)
            log_action("编辑人口数据", f"{data['region']} {data['year']}")
            flash("人口数据已更新。", "success")
            return redirect(url_for("records"))
        except (ValueError, sqlite3.IntegrityError) as error:
            flash(f"保存失败：{error}", "error")
    return render_page("编辑人口数据", "维护已有年度人口指标。", "records", RECORD_FORM_TEMPLATE, record=record)


@app.route("/records/<int:record_id>/delete", methods=["POST"])
@admin_required
def delete_record(record_id: int):
    record = delete_record_by_id(record_id)
    if record:
        log_action("删除人口数据", f"{record['region']} {record['year']}")
    flash("人口数据已删除。", "success")
    return redirect(url_for("records"))


@app.route("/analytics")
@login_required
def analytics():
    metric = request.args.get("metric", "total_population")
    metric = metric if metric in METRIC_LABELS else "total_population"
    rows = latest_records()
    bars = build_bars(rows, metric)
    body = """
    <section class="toolbar"><form class="filters" method="get"><select name="metric">{% for key, label in metric_labels.items() %}<option value="{{ key }}" {{ 'selected' if key == metric else '' }}>{{ label }}</option>{% endfor %}</select><button type="submit">切换指标</button></form></section>
    <section class="grid two">
      <div class="panel"><div class="panel-head"><h2>最新年份 {{ metric_labels[metric] }} 对比</h2></div><div class="bar-list wide">{% for bar in bars %}<div class="bar-row"><span>{{ bar.label }}</span><div><i style="width: {{ bar.width }}%"></i></div><strong>{{ bar.value }}</strong></div>{% endfor %}</div></div>
      <div class="panel"><div class="panel-head"><h2>地区趋势摘要</h2></div><table><thead><tr><th>地区</th><th>区间</th><th>人口变化</th><th>变化率</th><th>老龄化率</th><th>城镇化率</th></tr></thead><tbody>{% for item in stats %}<tr><td>{{ item.region }}</td><td>{{ item.first_year }}-{{ item.last_year }}</td><td>{{ item.change }}</td><td class="{{ 'bad' if item.percent < 0 else 'good' }}">{{ item.percent }}%</td><td>{{ item.aging_rate }}%</td><td>{{ item.urbanization_rate }}%</td></tr>{% endfor %}</tbody></table></div>
    </section>
    """
    return render_page("统计分析", "按指标查看地区排名与历史变化。", "analytics", body, bars=bars, metric=metric, stats=region_statistics())


@app.route("/global")
@login_required
def global_population():
    continent = request.args.get("continent", "").strip()
    summary = global_population_summary(continent)
    line = build_line_points(summary["trend_points"])
    bars = build_bars(summary["latest"][:8], "total_population", label_field="country")
    body = """
    <section class="toolbar">
      <form class="filters" method="get">
        <select name="continent">
          <option value="">全部洲</option>
          {% for item in continents %}<option value="{{ item }}" {{ 'selected' if item == continent else '' }}>{{ item }}</option>{% endfor %}
        </select>
        <button type="submit">统计</button>
      </form>
    </section>
    <section class="kpis">
      <article><span>最新年份</span><strong>{{ summary.latest_year or '-' }}</strong></article>
      <article><span>国家数量</span><strong>{{ summary.country_count }}</strong></article>
      <article><span>总人口</span><strong>{{ summary.total_population }}</strong><small>万人</small></article>
      <article><span>人口最多国家</span><strong>{{ summary.top_country }}</strong></article>
      <article><span>平均自然增长率</span><strong>{{ summary.avg_growth }}‰</strong></article>
      <article><span>平均老龄化率</span><strong>{{ summary.avg_aging }}%</strong></article>
    </section>
    <section class="grid two">
      <div class="panel">
        <div class="panel-head"><h2>{{ continent or '全球国家' }}人口趋势</h2><span>{{ line.min }} - {{ line.max }} 万人</span></div>
        <svg class="line-chart" viewBox="0 0 720 280" preserveAspectRatio="none">
          <line x1="0" y1="244" x2="720" y2="244"></line><polyline points="{{ line.polyline }}"></polyline>
          {% for item in line.labels %}<text x="{{ item.x }}" y="270">{{ item.label }}</text>{% endfor %}
        </svg>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>最新年份国家人口排行</h2><span>单位：万人</span></div>
        <div class="bar-list wide">{% for bar in bars %}<div class="bar-row"><span>{{ bar.label }}</span><div><i style="width: {{ bar.width }}%"></i></div><strong>{{ bar.value }}</strong></div>{% endfor %}</div>
      </div>
    </section>
    <section class="grid two global-tables">
      <div class="panel table-panel">
        <div class="panel-head"><h2>国家明细</h2></div>
        <table>
          <thead><tr><th>国家</th><th>洲</th><th>年份</th><th>总人口</th><th>出生率</th><th>死亡率</th><th>自然增长率</th><th>老龄化率</th><th>城镇化率</th></tr></thead>
          <tbody>{% for row in summary.latest %}<tr><td>{{ row.country }}</td><td>{{ row.continent }}</td><td>{{ row.year }}</td><td>{{ row.total_population }}</td><td>{{ row.birth_rate }}‰</td><td>{{ row.death_rate }}‰</td><td class="{{ 'bad' if row.natural_growth_rate < 0 else 'good' }}">{{ row.natural_growth_rate }}‰</td><td>{{ row.aging_rate }}%</td><td>{{ row.urbanization_rate }}%</td></tr>{% endfor %}</tbody>
        </table>
      </div>
      <div class="panel table-panel">
        <div class="panel-head"><h2>洲际汇总</h2></div>
        <table>
          <thead><tr><th>洲</th><th>国家数</th><th>总人口</th><th>平均增长率</th><th>平均老龄化率</th><th>平均城镇化率</th></tr></thead>
          <tbody>{% for row in summary.continent_summary %}<tr><td>{{ row.continent }}</td><td>{{ row.country_count }}</td><td>{{ row.total_population }}</td><td class="{{ 'bad' if row.avg_growth < 0 else 'good' }}">{{ row.avg_growth }}‰</td><td>{{ row.avg_aging }}%</td><td>{{ row.avg_urbanization }}%</td></tr>{% endfor %}</tbody>
        </table>
      </div>
    </section>
    """
    return render_page(
        "全球人口统计",
        "按国家和洲维度统计公开人口数据。",
        "global",
        body,
        summary=summary,
        line=line,
        bars=bars,
        continents=get_global_continents(),
        continent=continent,
    )


@app.route("/comparison")
@login_required
def comparison():
    selected = request.args.getlist("regions") or get_regions()[:3]
    year = request.args.get("year", "")
    years = get_years()
    if not year and years:
        year = str(max(years))
    rows = []
    if selected and year:
        placeholders = ",".join("?" for _ in selected)
        rows = query_all(
            f"SELECT * FROM population_records WHERE year = ? AND region IN ({placeholders}) ORDER BY total_population DESC",
            [year, *selected],
        )
    bars = build_bars(rows)
    body = """
    <section class="toolbar"><form class="filters" method="get"><select name="year">{% for item in years %}<option value="{{ item }}" {{ 'selected' if item|string == year else '' }}>{{ item }}</option>{% endfor %}</select><div class="check-group">{% for region in regions %}<label><input type="checkbox" name="regions" value="{{ region }}" {{ 'checked' if region in selected else '' }}> {{ region }}</label>{% endfor %}</div><button type="submit">对比</button></form></section>
    <section class="grid two"><div class="panel"><div class="panel-head"><h2>{{ year }} 年总人口对比</h2></div><div class="bar-list wide">{% for bar in bars %}<div class="bar-row"><span>{{ bar.label }}</span><div><i style="width: {{ bar.width }}%"></i></div><strong>{{ bar.value }}</strong></div>{% endfor %}</div></div><div class="panel table-panel"><table><thead><tr><th>地区</th><th>总人口</th><th>出生率</th><th>自然增长率</th><th>老龄化率</th><th>城镇化率</th></tr></thead><tbody>{% for row in rows %}<tr><td>{{ row.region }}</td><td>{{ row.total_population }}</td><td>{{ row.birth_rate }}‰</td><td class="{{ 'bad' if row.natural_growth_rate < 0 else 'good' }}">{{ row.natural_growth_rate }}‰</td><td>{{ row.aging_rate }}%</td><td>{{ row.urbanization_rate }}%</td></tr>{% endfor %}</tbody></table></div></section>
    """
    return render_page("地区对比", "选择多个地区，横向比较同一年的人口结构指标。", "comparison", body, regions=get_regions(), years=years, selected=selected, year=year, rows=rows, bars=bars)


@app.route("/forecast")
@login_required
def forecast():
    regions = get_regions()
    region = request.args.get("region", regions[0] if regions else "")
    metric = request.args.get("metric", "total_population")
    metric = metric if metric in METRIC_LABELS else "total_population"
    try:
        years_ahead = min(max(int(request.args.get("years", "3")), 1), 10)
    except ValueError:
        years_ahead = 3
    result = linear_forecast(region, metric, years_ahead) if region else None
    line = build_line_points([*result.history, *result.future] if result else [])
    body = """
    <section class="toolbar"><form class="filters" method="get"><select name="region">{% for item in regions %}<option value="{{ item }}" {{ 'selected' if item == region else '' }}>{{ item }}</option>{% endfor %}</select><select name="metric">{% for key, label in metric_labels.items() %}<option value="{{ key }}" {{ 'selected' if key == metric else '' }}>{{ label }}</option>{% endfor %}</select><input name="years" type="number" min="1" max="10" value="{{ years_ahead }}"><button type="submit">预测</button></form></section>
    {% if result %}<section class="grid two"><div class="panel"><div class="panel-head"><h2>{{ result.region }} {{ result.metric_label }} 趋势预测</h2><span>线性回归 y = {{ '%.2f'|format(result.slope) }}x + {{ '%.2f'|format(result.intercept) }}</span></div><svg class="line-chart" viewBox="0 0 720 280" preserveAspectRatio="none"><line x1="0" y1="244" x2="720" y2="244"></line><polyline points="{{ line.polyline }}"></polyline>{% for item in line.labels %}<text x="{{ item.x }}" y="270">{{ item.label }}</text>{% endfor %}</svg></div><div class="panel"><div class="panel-head"><h2>预测结果</h2></div><table><thead><tr><th>年份</th><th>{{ result.metric_label }}</th></tr></thead><tbody>{% for item in result.future %}<tr><td>{{ item.label }}</td><td>{{ item.value }}</td></tr>{% endfor %}</tbody></table></div></section>{% else %}<section class="panel empty">该地区数据不足，至少需要两年历史记录。</section>{% endif %}
    """
    return render_page("趋势预测", "基于历史数据进行简单线性回归预测。", "forecast", body, regions=regions, region=region, metric=metric, years_ahead=years_ahead, result=result, line=line)


@app.route("/charts")
@login_required
def charts():
    try:
        chart_paths = generate_charts()
    except ImportError:
        flash("当前环境未安装 Matplotlib，请执行 pip install -r requirements.txt。", "error")
        chart_paths = {}
    body = """
    <section class="grid two chart-grid">
      {% if chart_paths %}
      <div class="panel"><div class="panel-head"><h2>折线图：总体人口趋势</h2></div><img class="chart-img" src="{{ url_for('static', filename=chart_paths.trend) }}"></div>
      <div class="panel"><div class="panel-head"><h2>柱状图：地区人口排行</h2></div><img class="chart-img" src="{{ url_for('static', filename=chart_paths.ranking) }}"></div>
      <div class="panel"><div class="panel-head"><h2>饼图：性别结构</h2></div><img class="chart-img small-chart" src="{{ url_for('static', filename=chart_paths.gender) }}"></div>
      <div class="panel"><div class="panel-head"><h2>折线图：全球国家人口趋势</h2></div><img class="chart-img" src="{{ url_for('static', filename=chart_paths['global']) }}"></div>
      {% endif %}
    </section>
    """
    return render_page("数据可视化", "使用 Matplotlib 生成折线图、柱状图和饼图。", "charts", body, chart_paths=chart_paths)


@app.route("/alerts")
@login_required
def alerts():
    rows = get_alerts()
    body = """
    <section class="panel"><div class="panel-head"><h2>人口风险预警</h2><span>规则：老龄化率 ≥ 20%、自然增长率 &lt; 0、出生率 &lt; 7‰</span></div><div class="alert-list">{% for alert in rows %}<article class="alert-card"><strong>{{ alert.region }} · {{ alert.year }}</strong><span class="tag">{{ alert.level }}</span><ul>{% for reason in alert.reasons %}<li>{{ reason }}</li>{% endfor %}</ul><p>{{ alert.suggestion }}</p></article>{% else %}<div class="empty">当前最新年度数据没有触发预警。</div>{% endfor %}</div></section>
    """
    return render_page("风险预警", "自动识别人口结构和增长风险。", "alerts", body, rows=rows)


@app.route("/import", methods=["GET", "POST"])
@admin_required
def import_data():
    if request.method == "POST":
        try:
            count = import_csv_text(request.form.get("csv_text", ""))
            log_action("导入人口数据", f"CSV 导入 {count} 条")
            flash(f"已导入或更新 {count} 条数据。", "success")
            return redirect(url_for("records"))
        except ValueError as error:
            flash(f"导入失败：{error}", "error")
    sample = "region,year,total_population,male_population,female_population,birth_rate,death_rate,natural_growth_rate,aging_rate,urbanization_rate,source,note\\n浙江,2023,6627,3412,3215,6.97,6.20,0.77,16.2,74.1,CSV导入,示例"
    body = """
    <section class="panel form-panel"><form method="post"><label>CSV 内容<textarea name="csv_text" rows="12" placeholder="{{ sample }}"></textarea></label><div class="help">支持新增和按“地区 + 年份”覆盖更新。字段名请使用英文表头，便于后续导出与程序处理。</div><div class="form-actions"><button type="submit">导入数据</button></div></form></section>
    """
    return render_page("数据导入", "通过 CSV 文本批量新增或更新人口数据。", "import", body, sample=sample)


@app.route("/regions", methods=["GET", "POST"])
@login_required
def regions():
    if request.method == "POST":
        if g.user["role"] != "admin":
            flash("查看者不能新增地区档案。", "error")
        else:
            try:
                add_region(request.form)
                log_action("新增地区档案", request.form.get("name", "").strip())
                flash("地区档案已新增。", "success")
            except ValueError as error:
                flash(str(error), "error")
        return redirect(url_for("regions"))
    rows = query_all("SELECT * FROM regions ORDER BY name")
    body = """
    <section class="grid two"><div class="panel table-panel"><table><thead><tr><th>地区</th><th>类型</th><th>行政编码</th><th>说明</th></tr></thead><tbody>{% for row in rows %}<tr><td>{{ row.name }}</td><td>{{ row.category }}</td><td>{{ row.admin_code }}</td><td>{{ row.description }}</td></tr>{% endfor %}</tbody></table></div><div class="panel form-panel"><form method="post"><label>地区名称<input name="name"></label><label>地区类型<input name="category" value="省级行政区"></label><label>行政编码<input name="admin_code"></label><label>说明<textarea name="description" rows="5"></textarea></label><button type="submit">新增地区</button></form></div></section>
    """
    return render_page("地区档案", "维护地区基础资料，为人口数据提供元信息。", "regions", body, rows=rows)


@app.route("/logs")
@login_required
def logs():
    rows = query_all("SELECT * FROM operation_logs ORDER BY created_at DESC LIMIT 100")
    body = """
    <section class="panel table-panel"><table><thead><tr><th>时间</th><th>用户</th><th>操作</th><th>详情</th></tr></thead><tbody>{% for row in rows %}<tr><td>{{ row.created_at }}</td><td>{{ row.username }}</td><td>{{ row.action }}</td><td>{{ row.detail }}</td></tr>{% else %}<tr><td colspan="4" class="empty">暂无操作日志。</td></tr>{% endfor %}</tbody></table></section>
    """
    return render_page("操作日志", "记录关键数据维护行为。", "logs", body, rows=rows)


@app.route("/export")
@login_required
def export_records():
    rows = list_records(request.args.get("region", "").strip(), request.args.get("year", "").strip(), request.args.get("keyword", "").strip())
    log_action("导出人口数据", f"导出 {len(rows)} 条")
    return Response(
        records_to_csv(rows),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=population_records.csv"},
    )


if __name__ == "__main__":
    init_database()
    app.run(debug=True)
