
import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response
from datetime import datetime
from wtforms import TextField, BooleanField, PasswordField, IntegerField,SelectField,StringField, TextAreaField, DateField
from flask_wtf import Form
from wtforms.validators import *

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)
print os.getcwd()
app.secret_key = 'just a key'


DATABASEURI = "postgresql://xz2476:5rwzh@104.196.175.120/postgres"
engine = create_engine(DATABASEURI)

@app.before_request
def before_request():
  try:
    g.conn = engine.connect()
  except:
    print "uh oh, problem connecting to database"
    import traceback; traceback.print_exc()
    g.conn = None

@app.teardown_request
def teardown_request(exception):
  try:
    g.conn.close()
  except Exception as e:
    pass

#Homepage:
@app.route('/')
def homepage():
  return render_template("homepage.html")

#Customer:
class searchcust(Form):
  custid = SelectField("Customer ID: ",validators=[DataRequired()],coerce = str)

class addcust(Form):
  name = StringField('Name',validators=[InputRequired()])
  email = StringField('Email',validators=[InputRequired()])
  password = StringField('Password',validators=[InputRequired()])
  dob = DateField('Date of Birth(Y-m-d)',validators=[InputRequired()],format='%Y-%m-%d')
  gender = SelectField('Gender(Female/Male)',validators=[InputRequired()],choices = [('Female','Female'),('Male','Male')])
  phone = IntegerField('Phone', validators=[InputRequired(),NumberRange(min=1000000000,max=9999999999,message="Phone number should be 10 digits(no space)")])
  address = StringField('Address',validators=[InputRequired()])

@app.route('/Customer',methods = ['GET','POST'])
def search():
  total= g.conn.execute("SELECT count(*) FROM customer;")
  for row in total:
    t = row[0]
  form = searchcust()
  custid = []
  custlist = engine.execute("select distinct(customerid) from customer order by customerid ASC;")
  for row in custlist:
    custid.append(str(row[0]))
  form.custid.choices = zip(custid,custid)
  list = []
  order = []
  if form.validate_on_submit():
        id = form.custid.data
        info = g.conn.execute("SELECT * FROM customer WHERE customerid = %s", (id))
        for row in info:
           list.append(row)
        orders = g.conn.execute("SELECT * FROM orderdetail WHERE customerid = %s", (id))
        for row in orders:
          order.append(row)
        return render_template("cust_home.html", total=t, form = form, customer=list, order = order)

  return render_template("cust_home.html", total=t, form = form, customer=list, order = order)


#add customer:
@app.route('/Customer/add', methods= ['Post','GET'])
def add():
  form = addcust()
  if form.validate_on_submit():
    id = 0
    curid = g.conn.execute("select max(customerid) from customer;")
    for row in curid:
      id = row[0] + 1
    name = form.name.data
    email = form.email.data
    password = form.password.data
    dob = form.dob.data
    gender = form.gender.data
    phone = form.phone.data
    address = form.address.data
    g.conn.execute( "INSERT INTO customer VALUES (%s,%s,%s,%s,%s,%s,%s,%s);",(id),(name),(email),(password),(dob),(gender),(phone),(address))
    return redirect('/Customer/add')
  return render_template("customer_add.html",form = form)

#Check inventory before any orders:
@app.route('/Inventory',methods=['GET','POST'])
def check_inventory():
  idlist = []
  id = g.conn.execute("select distinct(itemid) from inventory order by itemid ASC;")
  for n in id:
    idlist.append(n[0])
  under = []
  under_l = g.conn.execute("select * from inventory where quantity < 10 order by quantity ASC;")
  for row in under_l:
    under.append(list(row))
  return render_template("inventory_check.html",idlist=idlist,under = under)

@app.route('/Inventory/color',methods=['get','post'])
def check_inventory_col():
  col = []
  id = request.form['id']
  size = request.form['size']
  cols = g.conn.execute("Select distinct(color) from inventory where itemid = %s and size = %s ;",(id),(size))
  for row in cols:
    col.append(row[0])
  return render_template("inventory_check_color.html",id = id, size = size, col = col)

@app.route('/Inventory/result',methods=['get','post'])
def inventory_result( ):
    id = request.form['id']
    size = request.form['size']
    color = request.form['color']
    info = g.conn.execute(
      "SELECT p.category,p.description,p.designer,p.material,p.price,i.quantity FROM inventory i, products p WHERE  i.itemid = p.itemid and i.size = p.size and i.color= p.color and i.itemid = %s  and i.size = %s  and i.color = %s",
      (id), (size), (color))
    storage = []
    for row in info:
      storage.append(list(row))

    wdist = []
    wdists = g.conn.execute(
      "select s.warehouseid, name, quantity from storage_log s,warehouse w where s.warehouseid = w.warehouseid and itemid = %s and size = %s and color = %s ",
      (id,size,color)
    )
    for row in wdists:
      wdist.append(list(row))

    return render_template("inventory_result.html", storage=storage,  size = size, id=id, color = color,wdist = wdist)

@app.route('/market',methods=['get','post'])
def market():
      mon = request.form['month']
      stat_p = "select itemid, size, color, sum(quantity) as sum from orderdetail where EXTRACT(MONTH FROM time) = %s group by itemid, size, color order by sum DESC;"
      popular = []
      populars = g.conn.execute(stat_p, (mon))
      for n in populars:
          popular.append(list(n))

      stat_d = "select designer, sum(quantity)as sum_qun,sum(quantity*discount*price) as sum_rev from orderdetail o,products p where o.itemid = p.itemid and o.size = p.size and o.color=p.color and EXTRACT(MONTH FROM time) = %s group by designer order by sum_rev DESC;"
      designer = []
      designers = g.conn.execute(stat_d,(mon))
      for n in designers:
        designer.append(list(n))
      return render_template("market.html",popular=popular,designer = designer)

@app.route('/log_order',methods=['get','post'])
def log_order():
  oid_new = 0
  custlist = []
  oid_list = g.conn.execute("select max(orderid) from orderdetail;")
  cust = g.conn.execute("select distinct(customerid) from customer order by customerid ASC;")
  for row in oid_list:
    oid_new = row[0]+1
  for row in cust:
    custlist.append(row[0])

  return render_template("log_order.html",oid_new = oid_new,custlist = custlist)

@app.route('/log_order/next',methods=['get','post'])
def log_order_next():
  oid = request.form['oid']
  cid = request.form['cid']
  idlist = []
  id = g.conn.execute("select distinct(itemid) from inventory order by itemid ASC;")
  for row in id:
    idlist.append(row[0])
  col = []
  cols = g.conn.execute("select distinct(color) from inventory;")
  for row in cols:
     col.append(row[0])
  return render_template('log_order_next.html',oid = oid, cid = cid, idlist = idlist,col = col)

@app.route('/log_order/submit',methods=['post','get'])
def log_order_submit():
  oid = request.form['oid']
  cid = request.form['cid']
  quantity = request.form['quantity']
  discount = request.form['discount']
  itemid = request.form['id']
  size = request.form['size']
  color = request.form['color']
  idlist = []
  id = g.conn.execute("select distinct(itemid) from inventory order by itemid ASC;")
  for row in id:
    idlist.append(row[0])
  col = []
  cols = g.conn.execute("select distinct(color) from inventory;")
  for row in cols:
    col.append(row[0])
  time = str(datetime.now())
  status = 'Successful'

  # add that record to orderdetial
  state = "insert into orderdetail VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
  g.conn.execute(state,(oid,cid,time,status,itemid,size,color,discount,quantity))
  return render_template("log_order_next.html",oid = oid, cid = cid, idlist = idlist, col=col)


@app.route('/Order',methods=['get','post'])
def order():
  custlist = []
  idlist = []
  col = []
  unfin = []
  id = g.conn.execute("select distinct(itemid) from inventory order by itemid ASC;")
  cust = g.conn.execute("select distinct(customerid) from customer order by customerid ASC;")
  cols = g.conn.execute("select distinct(color) from inventory;")
  unfinished = g.conn.execute("select * from orderdetail where status = 'Successful' order by orderid ASC;")
  for row in id:
    idlist.append(row[0])
  for row in cust:
    custlist.append(row[0])
  for row in cols:
     col.append(row[0])
  for row in unfinished:
    unfin.append(list(row))

  return render_template("order_check.html", idlist = idlist, custlist = custlist, col = col, unfin= unfin)


@app.route('/Order/result',methods=['get','post'])
def order_result():
  custid = request.form['custid']
  oid = request.form['oid']
  id = request.form['id']
  size = request.form['size']
  color = request.form['color']
  quantity = request.form['quantity']
  info = g.conn.execute("SELECT quantity,w.warehouseid, name, contact,contactphone,address FROM storage_log s, warehouse w WHERE  s.warehouseid = w.warehouseid and s.itemid = %s  and s.size = %s and s.color = %s",
    (id), (size), (color))
  storage = []
  for row in info:
    storage.append(list(row))
  custinfo = g.conn.execute("SELECT name, email,phone,address from customer where customerid= %s",(custid))
  custin = []
  for row in custinfo:
    custin.append(list(row))

  return render_template('order_result.html',custid=custid, oid = oid, id = id, size = size, color = color, quantity = quantity, storage = storage,custin = custin)

@app.route('/Order/result/submit',methods=['get','post'])
def order_sumit():
  custid = request.form['custid']
  oid = request.form['oid']
  id = request.form['id']
  size = request.form['size']
  color = request.form['color']
  quantity = request.form['quantity']
  wid = request.form['wid']

  #udate inventory table
  up_inven = "UPDATE orderdetail set status = 'Shipped' where orderid = %s and customerid = %s and itemid = %s and size = %s and color = %s;"
  g.conn.execute(up_inven,(oid,custid,id,size,color))

  #update storage log
  up_storage = "UPDATE storage_log set quantity = quantity - %s where itemid = %s and size = %s and color = %s and warehouseid = %s"
  g.conn.execute(up_storage,quantity,id,size,color,wid)

  return redirect('/Order')

@app.route('/Order/return',methods=['get','post'])
def returns():
  oids = []
  custlist = []
  idlist = []
  col = []
  oid_l = g.conn.execute("select distinct(orderid) from orderdetail order by orderid ASC;")
  id = g.conn.execute("select distinct(itemid) from orderdetail order by itemid ASC;")
  cust = g.conn.execute("select distinct(customerid) from orderdetail order by customerid ASC;")
  cols = g.conn.execute("select distinct(color) from orderdetail;")
  for row in id:
    idlist.append(row[0])
  for row in cust:
    custlist.append(row[0])
  for row in cols:
    col.append(row[0])
  for row in oid_l:
    oids.append(row[0])

  return render_template('log_return.html',oids = oids,idlist = idlist, custlist = custlist, col=col )

@app.route('/log_return/submit',methods=['get','post'])
def return_submit():
  oid = request.form['oid']
  cid = request.form['cid']
  id = request.form['id']
  size = request.form['size']
  color = request.form['color']
  up_order = "UPDATE orderdetail set status = 'Returned' where orderid = %s and customerid = %s and itemid = %s and size = %s and color = %s;"
  g.conn.execute(up_order,(oid,cid,id,size,color))
  return redirect('/Order/return')

@app.route('/restock',methods=['get','post'])
def restock():
  manu = []
  manus = g.conn.execute("select distinct(manufacturerid) from stock_log;")
  for row in manus:
    manu.append(row[0])

  idlist = []
  col = []
  id = g.conn.execute("select distinct(itemid) from inventory order by itemid ASC;")
  cols = g.conn.execute("select distinct(color) from inventory;")
  for row in id:
    idlist.append(row[0])
  for row in cols:
    col.append(row[0])
  return render_template('restock.html', manu=manu,idlist=idlist, col = col)

@app.route('/restock/next',methods=['get','post'])
def restock_next():
  mid = request.form['mid']
  id = request.form['id']
  size = request.form['size']
  color = request.form['color']
  quantity = request.form['quantity']
  manu = []
  manus = g.conn.execute("select * from manufacturer where manufacturerid = %s",(mid))
  for row in manus:
    manu.append(list(row))
  inven = []
  invens = g.conn.execute("select quantity, name, contact,contactphone, address from storage_log s, warehouse w where s.warehouseid = w.warehouseid and itemid = %s and size = %s and color = %s",(id,size,color))
  for row in invens:
    inven.append(list(row))
  return render_template('restock_check.html',mid = mid, id=id, size = size, color=color, quantity=quantity,manu = manu,inven= inven)

@app.route('/restock/submit',methods=['get','post'])
def restock_submit():
  mid = request.form['mid']
  id = request.form['id']
  size = request.form['size']
  color = request.form['color']
  quantity = request.form['quantity']

  manu = []
  manus = g.conn.execute("select * from manufacturer where manufacturerid = %s", (mid))
  for row in manus:
    manu.append(list(row))
  inven = []
  invens = g.conn.execute(
    "select quantity, name, contact,contactphone, address from storage_log s, warehouse w where s.warehouseid = w.warehouseid and itemid = %s and size = %s and color = %s",
    (id, size, color))
  for row in invens:
    inven.append(list(row))

  d1 = request.form['d1']
  d2 = request.form['d2']
  d3 = request.form['d3']
  d4 = request.form['d4']
  time = str(datetime.now())
  add_stock = "insert into stock_log values(%s,%s,%s,%s,%s,%s);"
  up_inven = "update inventory set quantity = quantity + %s where itemid = %s and size = %s and color = %s;"
  g.conn.execute(add_stock,(mid,id,size,color,quantity,time))
  g.conn.execute(up_inven,(quantity,id,size,color))

  up_storage = "update storage_log set quantity = quantity + %s where warehouseid = %s and itemid = %s and size = %s and color = %s;"
  g.conn.execute(up_storage,(d1,'1',id,size,color))
  g.conn.execute(up_storage,(d2,'2',id,size,color))
  g.conn.execute(up_storage,(d3,'3',id,size,color))
  g.conn.execute(up_storage,(d4,'4',id,size,color))

  return render_template('restock_check.html',mid = mid, id=id, size = size, color=color, quantity=quantity,manu = manu,inven= inven)

if __name__ == "__main__":
  import click

  @click.command()
  @click.option('--debug', is_flag=True)
  @click.option('--threaded', is_flag=True)
  @click.argument('HOST', default='0.0.0.0')
  @click.argument('PORT', default=8111, type=int)
  def run(debug, threaded, host, port):
    HOST, PORT = host, port
    print "running on %s:%d" % (HOST, PORT)
    app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)


  run()
