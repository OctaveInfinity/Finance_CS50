import os
import smtplib

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

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

    # Extract cash from our database
    cashier = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    cash = cashier[0]["cash"]

    # Extract symbol and shares of the stocks from our database
    rows = db.execute("SELECT symbol, shares FROM portfolios WHERE id=:id ORDER BY symbol ASC", id=session["user_id"])

    # If user HASN'T any stocks
    if not rows:
        # create and intialize new resulting table (dictionary with pairs key-value what according with our index.html)
        dataset = {'symbol': "No shares", 'name': "No shares", 'shares': 0, 'price': 0, 'sum': 0}
        return render_template("index.html", dataset=dataset, cash=cash, total=cash)

    # Else if user HAS some stocks
    else:

        for row in rows:

            # lookup of the stocks. uses lookup() function from helpers.py
            quote = lookup(row["symbol"])
            if quote == None:
                return apology("API is not responding", 400)
            # Calculate and add price to the rows
            price = quote["price"]
            row.update({'price': price})

            # Calculate and add name to the rows
            name = quote["name"]
            row.update({'name': name})

            # Calculate and add stocks summary to the rows  / summary by line
        # for row in rows:
            sum_line = row["price"] * row["shares"]
            row.update({'sum': sum_line})

        # Calculate summary by column (summary by line + cash)
        sums = 0
        for row in rows:
            sums += row["sum"]
        total = sums + cash

        return render_template("index.html", rows=rows, cash=cash, total=total)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # save session id for current user
    user_id = session["user_id"]

    # User reached route via POST (as by submitting a form)
    if request.method == "POST":

        symbol = request.form.get("symbol")
        if not symbol: # ensure symbol was submitted
            return apology("provide stock symbol", 400)

        shares = request.form.get("shares")
        if not shares: # ensure shares was submitted
            return apology("provide number of shares")
        elif not shares.isnumeric():
            return apology("provide numeric", 400)
        shares_entered = int(shares)

        # using helpers function to lookup online stock data for symbol
        symbol = symbol.upper()
        quote = lookup(symbol)
        # ensure symbol is valid stock data
        if quote == None:
            return apology("lookup failed, invalid symbol", 400)

        # create and calculate some temporary variables
        cash = db.execute ("SELECT cash FROM users WHERE id = :id", id = user_id)
        cash_available = cash[0]["cash"]
        price_quoted = quote["price"]
        price_buy = price_quoted * shares_entered
        cash_updated = cash_available - price_buy

        # ensure user has enough money to purchase this quote
        if cash_updated < 0 :
            return apology ("user has not enough money", 400)

        # update user table
        db.execute("UPDATE users SET cash = :cash \
                        WHERE id = :id",
                        cash = cash_updated,
                        id = user_id)

        # update portfolios table
        rows = db.execute ("SELECT * FROM portfolios \
                        WHERE id = :id and symbol = :symbol",
                        id = user_id,
                        symbol = symbol)

        # if user HASN'T shares with this symbol
        if len(rows) == 0 :
            db.execute ("INSERT INTO portfolios (id, symbol, shares) \
                        VALUES (:id, :symbol, :shares)",
                        id = user_id,
                        symbol = symbol,
                        shares = shares_entered)

        # he HAS them
        else:
            db.execute ("UPDATE portfolios SET shares = (shares + :shares) \
                        WHERE id = :id AND symbol=:symbol",
                        shares = shares_entered,
                        id = user_id,
                        symbol=symbol)

        # update history table
        db.execute ("INSERT INTO history (id, symbol, shares, price) \
                        VALUES (:id, :symbol, :shares, :price)",
                        id = user_id,
                        symbol = symbol,
                        shares = shares_entered,
                        price = price_quoted)

        # Display a flash message
        flash("BOUGHT !")

        # Redirect to index page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    return jsonify("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    rows = db.execute("SELECT * FROM history WHERE id=:id ORDER BY transacted DESC", id = session["user_id"])
    return render_template("history.html", history_list = rows)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("provide username", 401)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("provide password", 401)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                            username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect to index page
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

    # if user reached route via POST (as by submitting a form)
    if request.method == "POST":

        # ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("provide symbol")

        # turn all symbols entered by user in uppercase
        symbol = request.form.get("symbol").upper()

        # using helpers function to lookup online stock data for symbol
        quote = lookup(symbol)

        # ensure stock symbol in data
        if not quote:
            return apology("Invalid stock symbol", 400)
        # else return page with quotation
        else:
            return render_template("quoted.html",
                                    name=quote["name"],
                                    symbol=quote["symbol"],
                                    price=quote["price"])

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form)
    if request.method == "POST":

        # create and calculate some temporary variables
        username = request.form.get("username")
        password = request.form.get("password")
        hash=generate_password_hash(password)
        confirmation = request.form.get("confirmation")
        email = request.form.get("email") # can be empty

        # ensure all fields (exept email) was submitted
        if not username or not password or not confirmation:
            return apology("provide all fields", 400)

        # ensure password and password_confirmation are same
        elif not password == confirmation:
            return apology("Password and Confirmation must match", 400)

        # check if the username is unique in database
        result = db.execute("SELECT username FROM users \
                            WHERE username=:username",
                            username=username)
        if result:
            return apology("Username already exists", 400)


        # save submitted fields in database
        result = db.execute("INSERT INTO users (username, hash, email) \
                            VALUES (:username, :hash, :email)",
                            username=username, hash=hash, email=email)
        if not result:
            return apology("Failure insert user into database", 400)


        # query database for username
        rows = db.execute("SELECT * FROM users \
                            WHERE username = :username",
                            username=username)

        # remember user session
        session["user_id"] = rows[0]["id"]

        # SEND EMAIL about registration success
        #message = "You are registered!"
        #server = smtplib.SMTP("smtp.gmail.com", 587)
        #server.starttls()
        #server.login("e.makoviak@gmail.com", "...")
        #server.sendmail("e.makoviak@gmail.com", email, message)
        #server.quit()

        # display a flash message
        flash("REGISTERED !")

        # redirect to index page
        return redirect("/")


    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

    return apology("Register first", 403)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # take session id for current user
    user_id = session["user_id"]

    # scan all symbols for choicebox
    symbols = db.execute("SELECT symbol FROM portfolios WHERE id=:id", id=user_id)
    if not symbols:
        return apology("You don't have any stocks")

    # User reached route via POST (as by submitting a form)
    if request.method == "POST":

        # create, calculate some temporary variables
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        # check submited value
        if not symbol or not shares:
            return apology("provide all fields", 400)
        if not shares.isnumeric():
            return apology("provide numeric shares")
        shares_entered = int(shares)


        # lookup online stock data for this symbol
        symbol = symbol.upper()
        quote = lookup(symbol)
        if quote == None:
            return apology("lookup failed, invalid symbol")


        # if user HASN'T shares for this symbol
        result = db.execute ("SELECT shares FROM portfolios \
                            WHERE id = :id AND symbol = :symbol",
                            id = user_id, symbol = symbol)
        if not result:
            return apology("user hasn't shares with this symbol")

        # user HAS shares for this symbol
        else:
            rows = db.execute ("SELECT shares FROM portfolios \
                                WHERE id = :id AND symbol = :symbol",
                                id = user_id, symbol = symbol)

            shares_available = rows[0]["shares"]

            # if user HAS NOT ENOUGH shares to sell
            if shares_available < shares_entered:
                return apology ("user has not enough shares to sell")

            # HAS ENOUGH
            else:
                # create and calculate some temporary variables
                cash = db.execute ("SELECT cash FROM users WHERE id = :id", id = user_id)
                cash_available = cash[0]["cash"]
                price_quoted = quote["price"]
                price_sell = price_quoted * shares_entered
                cash_updated = cash_available + price_sell

                # update user table in database
                db.execute("UPDATE users SET cash = :cash WHERE id = :id",
                                cash = cash_updated, id = user_id)

                # if user has EXACTLY as many shares as he is trying to sell
                if shares_available == shares_entered:
                    db.execute("DELETE FROM portfolios \
                                WHERE symbol=:symbol AND id=:id",
                                symbol=symbol, id=user_id)
                else:
                    db.execute ("UPDATE portfolios SET shares = (shares - :shares) \
                                WHERE id = :id AND symbol=:symbol",
                                shares = shares_entered, id = user_id, symbol=symbol)

                # insert new row to the history table
                db.execute ("INSERT INTO history (id, symbol, shares, price) \
                                VALUES (:id, :symbol, :shares, :price)",
                                id = user_id, symbol = symbol,
                                shares = -shares_entered, price = price_quoted)

                # display a flash message
                flash("SOLD !")

                # redirect to index page
                return redirect("/")


    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html", symbols=symbols)
        #return render_template("sell.html")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
