import os

'''from cs50 import SQL'''
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
''' I am doing some changes'''

''' added forth line'''
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
    """Show portfolio of stocks"""
    symbols = []
    names = []
    sharess = []
    prices = []
    totals = []
    result = db.execute("SELECT * FROM 'portfolio' WHERE userid = :userid", userid=session["user_id"])
    length = len(result)
    result2 = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
    cash = result2[0]['cash']
    total = cash
    for n in range(len(result)):
        my_dict = lookup(result[n]['symbol'])
        symbols.append(my_dict['symbol'])
        names.append(my_dict['name'])
        sharess.append(result[n]['shares'])
        prices.append(usd(my_dict['price']))
        totals.append(usd(my_dict['price']*result[n]['shares']))
        total = total + my_dict['price']*result[n]['shares']

    return render_template("index.html", symbols=symbols, names=names, sharess=sharess, prices=prices, totals=totals, length=length, cash=usd(cash), total=usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        shares = request.form.get("shares")
        symbol = request.form.get("symbol")
        if not symbol or not shares:
            return apology("missing symbol", 400)
        elif not lookup(symbol):
            return apology("invaild symbol", 400)
        elif not int(shares) > 0 or type(int(shares)) is not int:
            return apology("Share must be greater than 0", 400)

        userid = session["user_id"]
        my_dict = lookup(symbol)
        rows = db.execute("SELECT cash FROM users WHERE id = :userid", userid=userid)
        cash = float(rows[0]["cash"])
        symbol = my_dict["symbol"]
        shares = int(request.form.get("shares"))
        price = float(my_dict["price"])
        total = price * shares

        if cash < total:
            return apology("can't afford", 400)
        db.execute("INSERT INTO 'transaction' (userid,symbol,shares,price) VALUES (:userid,:symbol,:shares,:price)",
                   userid=userid, symbol=symbol, shares=shares, price=usd(price))

        db.execute("UPDATE users SET cash = cash - :total WHERE id = :userid", total=total, userid=userid)
        if db.execute("SELECT symbol FROM 'portfolio' WHERE userid= :userid AND symbol = :symbol", userid=userid, symbol=symbol):
            db.execute("UPDATE 'portfolio' SET shares = shares + :shares WHERE userid= :userid AND symbol = :symbol ",
                       shares=shares, userid=userid, symbol=symbol)
        else:
            db.execute("INSERT INTO 'portfolio' (userid, symbol, shares) VALUES (:userid, :symbol, :shares)",
                       userid=userid, symbol=symbol, shares=shares)

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    transaction = db.execute("SELECT * FROM 'transaction' WHERE userid = :userid", userid=session["user_id"])
    return render_template("history.html", transaction=transaction, length=len(transaction))


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
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)
        symbol = request.form.get("symbol")
        if lookup(symbol):
            my_dict = lookup(symbol)
            return render_template("quoted.html", name=my_dict['name'], price=usd(my_dict['price']), sym=my_dict['symbol'])
        else:
            return apology("invalid symbol", 400)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password is correct
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("not same password", 400)
        # Insert database for username
        result = db.execute("INSERT INTO users (username,hash) VALUES (:username, :password)",
                            username=request.form.get("username"),
                            password=generate_password_hash(request.form.get("password")))
        if not result:
            return apology("Try different username", 400)
        # Redirect user to home page
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    stock = list()
    stockvalue = 0
    userid = session["user_id"]
    """Sell shares of stock"""
    sell = db.execute("SELECT symbol FROM 'portfolio' WHERE userid = :userid", userid=userid)

    for n in range(len(sell)):
        stock.append(sell[n]["symbol"])

    if request.method == "POST":
        shares = int(request.form.get("shares"))
        symbol = request.form.get("symbol")
        selectedstock = db.execute("SELECT shares FROM 'portfolio' WHERE userid = :userid AND symbol = :symbol ",
                                   userid=userid, symbol=symbol)
        stockvalue = int(selectedstock[0]["shares"])
        if shares > stockvalue:
            return apology("too much shares", 400)
        my_dict = lookup(symbol)
        price = float(my_dict["price"])
        gain = price * shares

        db.execute("INSERT INTO 'transaction' (userid,symbol,shares,price) VALUES (:userid,:symbol,:shares,:price)",
                   userid=userid, symbol=symbol, shares=-shares, price=usd(price))
        if shares == stockvalue:
            db.execute("DELETE FROM 'portfolio' WHERE userid = :userid AND symbol = :symbol", userid=userid, symbol=symbol)
        else:
            db.execute("UPDATE 'portfolio' SET shares = shares - :shares WHERE userid = :userid AND symbol = :symbol",
                       shares=shares, userid=userid, symbol=symbol)
        db.execute("UPDATE users SET cash = cash + :gain WHERE id = :userid", gain=gain, userid=userid)
        return redirect("/")

    return render_template("sell.html", stock=stock)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
