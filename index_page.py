from flask import Blueprint, Flask, render_template, request, jsonify
from sqlalchemy import func

from models import House
index_page=Blueprint('index',__name__,template_folder='templates')
@index_page.route('/')
def index():
    total_houses=House.query.count()
    latest_houses=House.query.order_by(House.publish_time.desc()).limit(5).all()
    hot_houses=House.query.order_by(House.publish_time.desc()).all()
    return render_template("index.html",total_houses=total_houses,latest_houses=latest_houses,hot_houses=hot_houses)

@index_page.route('/search/keyword/',methods=['POST'])
def search_keyword():

    print(request.method)
    kw=request.form.get('kw')

    info =request.form.get('info')
    if info == "地区搜索":
        houselist=House.query.with_entities(House.address,func.count()).filter(House.address.contains(kw)).group_by(House.address)
        print(houselist)
        houselistdic=[]
        if len(houselist):
            for house in houselist:

                houselistdic.append({"t_name":house[0],"num":house[1]})
            return jsonify({"code":0,"info":houselistdic})

        else:
            return jsonify({"code":0,"info":houselistdic})

    return "search_keyword"