import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Ensure environment variable is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    cash=db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
    stocks=db.execute("SELECT stock, shares, total, price FROM portfolio WHERE id=:id", id=session["user_id"])
    if not stocks:
        return render_template("index1.html", cash=usd(cash[0]['cash']))
    else:
        prices=db.execute("SELECT stock, shares, total, price FROM portfolio WHERE id=:id", id=session["user_id"])
        for price in prices:
            symbol=prices[0]['stock']
            price = lookup(symbol)['price']
            shares=prices[0]['shares']
            total=price*shares
            db.execute("UPDATE portfolio SET price=:price, total=:total WHERE id=:id AND stock=:symbol", price=price,
                    total=total, id=session["user_id"], symbol=symbol)

        sumnums=db.execute("SELECT SUM(total) AS \"sumnums\" FROM portfolio WHERE id=:id", id=session["user_id"])
        if sumnums:
            grand_total=sumnums[0]['sumnums']+(cash[0]['cash'])
        else:
            grand_total=cash[0]['cash']
        return render_template("index.html", cash = usd(cash[0]['cash']), grand_total=usd(grand_total), stocks=stocks)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method=="POST":
    # return apology if user does not enter a symbol
        if not request.form.get("symbol"):
            return apology("Must provide stock symbol!", 400)

    # return apology if user does not enter a number of shares or if that number is not a positive integer
        if not request.form.get("shares") or not request.form.get("shares").isdigit() or float(request.form.get("shares"))%1!=0 or int(request.form.get("shares"))<=0:
            return apology("Invalid number!", 400)

    # attempt to look up the submitted stock symbol, return apology upon failure
        lookedup=lookup(request.form.get("symbol"))
        if not lookedup:
            return apology("Invalid stock symbol!", 400)

    # retrieve the user's cash from the database
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])

    # calculate the value of the requested stock
        value = lookedup["price"] * int(request.form.get("shares"))

    # return apology if value exceeds the amount of cash in the user's account
        if value > cash[0]['cash']:
            return apology("You too poor for that", 400)

    # update transactions table with purchase
        transaction=db.execute("INSERT INTO transactions (id, worth, shares, symbol, purchase, price) VALUES(:id, :worth, :shares, :symbol, :purchase, :price)",
            id=session["user_id"], worth=value, shares=int(request.form.get("shares")), symbol=request.form.get("symbol"), price=lookedup["price"], purchase="purchase")

    # update portfolio table
        update=db.execute("SELECT shares FROM portfolio WHERE id=:id AND stock=:symbol",
                id=session["user_id"], symbol=request.form.get("symbol"))
        if not update:
            db.execute("INSERT INTO portfolio (id, stock, shares, price, total) VALUES(:id, :symbol, :shares, :total, :price)",
                id=session["user_id"], symbol=request.form.get("symbol"), shares=int(request.form.get("shares")), total=value, price=lookedup['price'])
        else:
            new_shares=update[0]['shares']+int(request.form.get('shares'))
            new_total=new_shares*lookedup['price']
            db.execute("UPDATE portfolio SET shares=:shares, total=:total, price=:price WHERE id=:id and stock=:symbol",
                shares=new_shares, total=new_total, id=session["user_id"], symbol=request.form.get("symbol"), price=lookedup['price'])

    # determine user's new cash and update it in the users table
        new_cash = cash[0]['cash'] - value
        update = db.execute("UPDATE users SET cash = :value WHERE id = :id", value = new_cash, id = session["user_id"])
        return render_template("bought.html", cash=usd(new_cash), price=usd(lookedup['price']), total=usd(value), shares=request.form.get("shares"), symbol=request.form.get("symbol"))
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    transactions=db.execute("SELECT symbol, shares, price, time, purchase FROM transactions WHERE id=:id", id=session["user_id"])
    return render_template("history.html", transactions=transactions)
    """Show history of transactions"""
    return apology("TODO")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Symbol required", 400)
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("Symbol not found!", 400)
        else:
            symbol = stock["symbol"]
            price = stock["price"]
            return render_template("quoted.html", symbol = symbol, price = usd(price))
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("Missing username!", 400)
        if not request.form.get("password"):
            return apology("Must provide password!", 400)
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords do not match!", 400)
        hash1 = generate_password_hash(request.form.get("password"))
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=request.form.get("username"), hash = hash1)
        if not result:
            return apology("Username already exists!", 400)
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                username = request.form.get("username"))
        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method=="POST":
        if not request.form.get("shares") or float(request.form.get("shares"))%1!=0 or int(request.form.get("shares"))<=0:
            return apology("Invalid number!", 400)
        if not request.form.get("symbol"):
            return apology("Pick a stock!", 400)
        num=db.execute("SELECT shares FROM portfolio WHERE id=:id and stock=:stock", id=session["user_id"], stock=request.form.get("symbol"))
        total=db.execute("SELECT total FROM portfolio WHERE id=:id and stock=:stock", id=session["user_id"], stock=request.form.get("symbol"))
        if num[0]["shares"]<int(request.form.get("shares")):
            return apology("You don't have that many shares to sell!", 400)
        else:
            lookedup=lookup(request.form.get("symbol"))
            value=lookedup["price"]*int(request.form.get("shares"))
            # update transactions table with sale
            transaction=db.execute("INSERT INTO transactions (id, worth, shares, symbol, purchase, price) VALUES(:id, :worth, :shares, :symbol, :purchase, :price)",
                id=session["user_id"], worth=value, shares=int(request.form.get("shares")), symbol=request.form.get("symbol"), purchase="sale", price=lookedup['price'])
            # update portfolio table
            new_shares=num[0]["shares"]-int(request.form.get("shares"))
            new_total=total[0]["total"]-value
            if new_shares==0:
                db.execute("DELETE FROM portfolio WHERE id=:id and stock=:symbol", id=session["user_id"], symbol=request.form.get("symbol"))
            else:
                db.execute("UPDATE portfolio SET shares=:shares, total=:total WHERE id=:id and stock=:symbol",
                shares=new_shares, total=new_total, id=session["user_id"], symbol=request.form.get("symbol"))
            # determine user's new cash and update it in the users table
            cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
            new_cash = cash[0]['cash'] + value
            db.execute("UPDATE users SET cash = :value WHERE id = :id", value = new_cash, id = session["user_id"])
            return render_template("sold.html", cash=usd(new_cash), total=usd(value), shares=request.form.get("shares"), symbol=request.form.get("symbol"), price=lookedup['price'])
    else:
        stocks=db.execute("SELECT stock FROM portfolio WHERE id=:id", id=session["user_id"])
        names=[]
        for item in stocks:
            names.append(item["stock"])
        return render_template("sell.html", names=names)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
