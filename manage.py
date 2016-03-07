#!/usr/bin/env python
# -*- coding:utf-8 *-*
import os
import zipfile

from app import setup_app, db
from flask.ext.script import Manager, Shell
from datetime import datetime as dte

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = setup_app()
manager = Manager(app)


def make_shell_context():
    import app.models as m
    import app.flow as f
    return dict(app=app, db=db, m=m, f=f)

manager.add_command("shell", Shell(make_context=make_shell_context))


@manager.command
def init_account(site):
    from app.models import get_rebot_class
    for cls in get_rebot_class(site):
        cls.login_all()


@manager.command
def cron():
    from cron import main
    main()


@manager.command
def test(coverage=False):
    cov = None
    if coverage:
        import coverage
        cov = coverage.coverage(branch=True, include="app/*")
        cov.start()
    import unittest
    tests = unittest.TestLoader().discover("tests")
    unittest.TextTestRunner(verbosity=2).run(tests)
    if cov:
        cov.stop()
        cov.save()
        print "coverage test result:"
        cov.report()
        covdir = os.path.join(BASE_DIR, 'tmp/covrage')
        cov.html_report(directory=covdir)
        print "Html version: file://%s/index.html" % covdir
        cov.erase()


@manager.command
def create_user(type):
    import getpass
    from app.models import AdminUser
    from app.utils import md5
    if type not in ["kefu", "admin"]:
        print "fail, the right command should like 'python manage.py create_user (kefu or admin)'"
        return
    username = raw_input("用户名:")
    try:
        u = AdminUser.objects.get(username=username)
        print "已存在用户, 创建失败"
        return
    except AdminUser.DoesNotExist:
        pass
    pwd1 = getpass.getpass('密码: ')
    pwd2 = getpass.getpass('确认密码: ')
    if pwd1 != pwd2:
        print "两次输入密码不一致, 创建用户失败"
        return
    u = AdminUser(username=username, password=md5(pwd1))
    if type == "kefu":
        u.is_kefu = 1
        u.is_switch = 0
        u.is_admin = 0
    elif type == "admin":
        u.is_kefu = 0
        u.is_switch = 0
        u.is_admin = 1

    u.save()
    print "创建用户成功"


@manager.command
def reset_password():
    import getpass
    from app.models import AdminUser
    from app.utils import md5
    username = raw_input("用户名:")
    try:
        u = AdminUser.objects.get(username=username)
        pwd1 = getpass.getpass('密码: ')
        pwd2 = getpass.getpass('确认密码: ')
        if pwd1 != pwd2:
            print "两次输入密码不一致, 重设密码失败"
            return
        u.modify(password=md5(pwd1))
        print "重设密码成功"
    except AdminUser.DoesNotExist:
        print "不存在用户", username


@manager.command
def clear_expire_line():
    from app.models import Line
    today = dte.now().strftime("%Y-%m-%d")
    cnt = Line.objects.filter(drv_date__lt=today).delete()
    app.logger.info("%s line deleted", cnt)


@manager.command
def add_pay_record(directory):
    from pay import import_alipay_record
    for par, dirs, files in os.walk(directory):
        for name in files:
            filename = os.path.join(par, name)
            if filename.endswith(".zip"):
                z = zipfile.ZipFile(filename, "r")
                for filename in z.namelist():
                    with z.open(filename) as f:
                        import_alipay_record(f)
            else:
                with open(filename, "r") as f:
                    import_alipay_record(f)


@manager.option('-s', '--site', dest='site', default='')
@manager.option('-p', '--province_name', dest='province_name',default='')
def sync_open_city(site, province_name):
    from app.models import OpenCity, Line
    from pypinyin import lazy_pinyin
    if not province_name:
        print 'province_name is null '
        return
    lines = Line.objects.filter(crawl_source=site, s_province=province_name).distinct('s_city_name')
    print lines
    for i in lines:
        openObj = OpenCity()
        openObj.province = province_name
        city_name = i
        if len(city_name) > 2 and (city_name.endswith('市') or city_name.endswith('县')):
            city_name = city_name[0:-1]
        openObj.city_name = city_name
        city_code = "".join(map(lambda w: w[0], lazy_pinyin(city_name.decode("utf-8"))))
        openObj.city_code = city_code
        openObj.pre_sell_days = 5
        openObj.open_time = "23:00"
        openObj.end_time = "8:00"
        openObj.advance_order_time = 60
        openObj.max_ticket_per_order = 3
        openObj.crawl_source = site
        openObj.is_active = True
        try:
            openObj.save()
            print openObj.city_name
        except:
            print '%s already existed'%city_name
            pass

if __name__ == '__main__':
    manager.run()
