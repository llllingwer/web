from flask import Flask, render_template, request, redirect, url_for
from flask import Blueprint
detail_page = Blueprint('detail_page', __name__)
@detail_page.route('/')
