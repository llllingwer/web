# app.py

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session,
)
from sqlalchemy import or_

from settings import app, db
from models import House, User, Recommend
import math
from index_page import index_page
from search_list import search_list
app.register_blueprint(search_list,url_prefix='/')
app.register_blueprint(index_page,url_prefix='/')

# --- 首页与列表页 ---


@app.route('/')
def index():
    """首页"""
    # 查询浏览量最高的8个房源作为热点推荐
    hot_houses = House.query.order_by(House.page_views.desc()).limit(8).all()
    # 查询最新发布的6个房源
    new_houses = House.query.order_by(House.publish_time.desc()).limit(6).all()

    # 获取登录用户信息
    user_name = session.get('user_name')
    user = User.query.filter_by(name=user_name).first() if user_name else None

    return render_template(
        'index.html',
        hot_houses=hot_houses,
        new_houses=new_houses,
        user=user
    )


@app.route('/list/<string:category>/<int:page>')
def house_list(category, page):
    """
    房源列表页
    :param category: 类别 (pattern: 默认模式, hot_house: 热点房源)
    :param page: 页码
    """
    per_page = 10  # 每页显示10条数据

    if category == 'pattern':
        # 按发布时间降序排序
        pagination = House.query.order_by(House.publish_time.desc()).paginate(page, per_page, error_out=False)
    elif category == 'hot_house':
        # 按浏览量降序排序
        pagination = House.query.order_by(House.page_views.desc()).paginate(page, per_page, error_out=False)
    else:
        # 默认排序
        pagination = House.query.paginate(page, per_page, error_out=False)

    houses = pagination.items

    user_name = session.get('user_name')
    user = User.query.filter_by(name=user_name).first() if user_name else None

    return render_template('list.html', houses=houses, pagination=pagination, user=user)


# --- 搜索功能 ---

@app.route('/query')
def query():
    """处理搜索请求并跳转到搜索结果列表"""
    addr = request.args.get('addr')
    rooms = request.args.get('rooms')

    # 将搜索条件存入session，以便结果页使用
    session['search_addr'] = addr
    session['search_rooms'] = rooms

    return redirect(url_for('search_result', page=1))


@app.route('/search_result/<int:page>')
def search_result(page):
    """显示搜索结果"""
    per_page = 10
    addr = session.get('search_addr')
    rooms = session.get('search_rooms')

    query = House.query
    if addr:
        # 支持区域、商圈、小区的模糊搜索
        query = query.filter(or_(
            House.region.like(f"%{addr}%"),
            House.block.like(f"%{addr}%"),
            House.address.like(f"%{addr}%")
        ))
    if rooms:
        query = query.filter(House.rooms.like(f"%{rooms}%"))

    pagination = query.order_by(House.publish_time.desc()).paginate(page, per_page, error_out=False)
    houses = pagination.items

    user_name = session.get('user_name')
    user = User.query.filter_by(name=user_name).first() if user_name else None

    # 此处假设您有一个'search_list.html'模板来展示搜索结果
    # 如果没有，可以复用'list.html'，只需稍作修改
    return render_template('list.html', houses=houses, pagination=pagination, user=user)


@app.route('/search/keyword/', methods=['POST'])
def search_keyword():
    """智能搜索关键词提示 (AJAX)"""
    keyword = request.form.get('kw', '')
    info_type = request.form.get('info', '')

    if not keyword:
        return jsonify(code=0, info='关键词为空')

    results = []
    if '地区' in info_type:
        # 搜索区域、商圈、小区
        houses = House.query.filter(or_(
            House.region.like(f'%{keyword}%'),
            House.block.like(f'%{keyword}%'),
            House.address.like(f'%{keyword}%')
        )).limit(10).all()

        # 示例数据结构
        results = [{'t_name': f"{h.region}-{h.block}-{h.address}", 'num': 1} for h in houses]

    elif '户型' in info_type:
        # 搜索户型
        houses = House.query.filter(House.rooms.like(f'%{keyword}%')).limit(10).all()
        results = [{'t_name': h.rooms, 'num': 1} for h in houses]

    if not results:
        return jsonify(code=0, info=f'未找到关于{keyword}的房屋信息！')

    return jsonify(code=1, info=results)


# --- 房源详情页 ---

@app.route('/house/<int:house_id>')
def house_detail(house_id):
    """房源详情页"""
    house = House.query.get_or_404(house_id)

    # 增加浏览量
    house.page_views = (house.page_views or 0) + 1
    db.session.commit()

    # 根据当前房源的小区推荐相似房源
    recommendations = House.query.filter(
        House.address == house.address,
        House.id != house.id
    ).limit(6).all()

    user_name = session.get('user_name')
    user = User.query.filter_by(name=user_name).first() if user_name else None

    if user:
        # 记录用户浏览历史
        seen_ids = user.seen_id.split(',') if user.seen_id else []
        if str(house_id) not in seen_ids:
            seen_ids.append(str(house_id))
            user.seen_id = ','.join(seen_ids)
            db.session.commit()

    return render_template('detail_page.html', house=house, recommendations=recommendations, user=user)


# --- 用户认证 ---

@app.route('/login', methods=['POST'])
def login():
    """用户登录"""
    username = request.form.get('username')
    password = request.form.get('password')

    user = User.query.filter_by(name=username, password=password).first()

    if user:
        session['user_id'] = user.id
        session['user_name'] = user.name
        return redirect(url_for('index'))
    else:
        # 实际项目中应返回错误提示
        return redirect(url_for('index'))


@app.route('/register', methods=['POST'])
def register():
    """用户注册"""
    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email')

    # 检查用户名是否已存在
    if User.query.filter_by(name=username).first():
        # 用户名已存在，应返回错误提示
        return redirect(url_for('index'))

    new_user = User(name=username, password=password, email=email)
    db.session.add(new_user)
    db.session.commit()

    # 注册成功后自动登录
    session['user_id'] = new_user.id
    session['user_name'] = new_user.name

    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    """用户登出"""
    session.clear()
    return jsonify(valid='1', msg='已退出登录')


# --- 用户中心 ---

@app.route('/user/<string:username>')
def user_page(username):
    """用户个人主页"""
    if 'user_name' not in session or session['user_name'] != username:
        return redirect(url_for('index'))

    user = User.query.filter_by(name=username).first_or_404()

    # 获取收藏的房源
    collected_houses = []
    if user.collect_id:
        collect_ids = [int(i) for i in user.collect_id.split(',') if i]
        collected_houses = House.query.filter(House.id.in_(collect_ids)).all()

    # 获取浏览记录
    seen_houses = []
    if user.seen_id:
        seen_ids = [int(i) for i in user.seen_id.split(',') if i]
        seen_houses = House.query.filter(House.id.in_(seen_ids)).all()

    return render_template('user_page.html', user=user, collected_houses=collected_houses, seen_houses=seen_houses)


@app.route('/add/collection/<int:house_id>')
def add_collection(house_id):
    """添加收藏 (AJAX)"""
    if 'user_id' not in session:
        return jsonify(valid='0', msg='请先登录！')

    user = User.query.get(session['user_id'])

    collect_ids = user.collect_id.split(',') if user.collect_id else []
    if str(house_id) not in collect_ids:
        collect_ids.append(str(house_id))
        user.collect_id = ','.join(filter(None, collect_ids))  # 过滤空字符串
        db.session.commit()
        return jsonify(valid='1', msg='收藏成功！')
    else:
        return jsonify(valid='0', msg='您已收藏过该房源！')


@app.route('/collect_off', methods=['POST'])
def collect_off():
    """取消收藏 (AJAX)"""
    house_id = request.form.get('house_id')
    user_name = request.form.get('user_name')

    if session.get('user_name') != user_name:
        return jsonify(valid='0', msg='用户验证失败！')

    user = User.query.filter_by(name=user_name).first()
    if not user or not user.collect_id:
        return jsonify(valid='0', msg='操作失败！')

    collect_ids = user.collect_id.split(',')
    if house_id in collect_ids:
        collect_ids.remove(house_id)
        user.collect_id = ','.join(collect_ids)
        db.session.commit()
        return jsonify(valid='1', msg='已取消收藏')
    return jsonify(valid='0', msg='未找到该收藏记录')


@app.route('/del_record', methods=['POST'])
def del_record():
    """清空浏览记录 (AJAX)"""
    user_name = request.form.get('user_name')
    if session.get('user_name') != user_name:
        return jsonify(valid='0', msg='用户验证失败！')

    user = User.query.filter_by(name=user_name).first()
    if user:
        user.seen_id = ''
        db.session.commit()
        return jsonify(valid='1', msg='浏览记录已清空')
    return jsonify(valid='0', msg='操作失败')


@app.route('/modify/userinfo/<string:field>', methods=['POST'])
def modify_userinfo(field):
    """修改用户信息 (AJAX)"""
    if 'user_name' not in session:
        return jsonify(ok='0')

    user = User.query.filter_by(name=session['user_name']).first()
    if not user:
        return jsonify(ok='0')

    if field == 'name':
        new_name = request.form.get('name')
        # 检查新用户名是否已存在
        if User.query.filter(User.name == new_name).first():
            return jsonify(ok='0', msg='用户名已存在')
        user.name = new_name
        session['user_name'] = new_name  # 更新session
    elif field == 'addr':
        user.addr = request.form.get('addr')
    elif field == 'pd':
        user.password = request.form.get('pd')
    elif field == 'email':
        user.email = request.form.get('email')
    else:
        return jsonify(ok='0')

    db.session.commit()
    return jsonify(ok='1')


# --- 数据可视化接口 (示例) ---
# 这些接口为详情页的图表提供数据，这里返回示例数据
# 在实际项目中，需要根据数据库中的数据进行计算和聚合

@app.route('/get/scatterdata/<region>')
def get_scatter_data(region):
    # 示例：返回价格和面积的散点图数据
    return jsonify(data=[[10, 8.04], [8, 6.95], [13, 7.58]])


@app.route('/get/piedata/<region>')
def get_pie_data(region):
    # 示例：返回户型占比饼图数据
    return jsonify(data=[
        {'value': 335, 'name': '2室1厅'},
        {'value': 310, 'name': '3室1厅'},
        {'value': 234, 'name': '1室1厅'}
    ])


@app.route('/get/columndata/<region>')
def get_column_data(region):
    # 示例：返回小区房源数量柱状图数据
    return jsonify(data={
        'x_axis': ['小区A', '小区B', '小区C'],
        'y_axis': [120, 200, 150]
    })


@app.route('/get/brokenlinedata/<region>')
def get_broken_line_data(region):
    # 示例：返回户型价格走势折线图数据
    return jsonify(data={
        'legend': ['2室1厅', '3室1厅'],
        'x_axis': ['1月', '2月', '3月'],
        'series': [
            {'name': '2室1厅', 'type': 'line', 'data': [3000, 3200, 3100]},
            {'name': '3室1厅', 'type': 'line', 'data': [4500, 4600, 4800]}
        ]
    })


if __name__ == '__main__':
    # 第一次运行时，需要创建数据库和表
    # 在命令行中进入python环境，执行 from app import db; db.create_all()
    app.run(debug=True)