from flask import Flask, render_template, request, redirect, url_for
from flask import Blueprint
search_list = Blueprint('search_bp', __name__)
@search_list.route('query',methods=['POST'])
def query():
    print(query)
