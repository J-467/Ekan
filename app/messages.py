from flask import current_app, g
from flask import (Blueprint, request)
from . import db
from collections import defaultdict

bp = Blueprint('messages', __name__)

EMPTY = 0 
INTRO = 1
INITIAL = 2
PRODUCT = 3
QUANTITY = 4
PRICE = 5
CONFIRMATION = 6
FINAL = 7
END = 8

sessions = {}
seshtrans = defaultdict(dict)

@bp.route('/', methods=['GET', 'POST'])
def ussd():
    session_id = request.values.get('sessionId', None)
    # service_code = request.values.get('serviceCode', None)
    phone_number = request.values.get('phoneNumber', None)
    text = request.values.get('text', None)
    dbs = db.get_db()
    user = dbs.execute('SELECT * FROM user WHERE number = ?', (phone_number,)).fetchone()
    if user:
        level = sessions.get(session_id, INTRO)
        print("sessions: ", sessions)
        print("level is: ", level)
        sessions[session_id] = level
        resp = process_msg(text, phone_number, session_id, level)
    else:
        resp = process_msg(text, phone_number, session_id, EMPTY)
    return resp

def process_msg(text, phone_number, session_id, level):
    dbs = db.get_db()
    msg = ""
    if level == EMPTY:
        dbs.execute('INSERT OR IGNORE INTO user (number) VALUES (?)', (phone_number,))
        sessions[session_id] = INTRO # the next level
        msg = create_message(EMPTY)
        dbs.commit()
    elif level == INTRO: # handle the name provision
        if text == "":
            name = dbs.execute('SELECT name FROM user WHERE number = ?', (phone_number,)).fetchone()[0]
        else:
            name = text.split("*")[-1]
            dbs.execute('UPDATE user SET name = ? WHERE number = ?', (name, phone_number))
            dbs.commit()
        
        sessions[session_id] = INITIAL
        msg = create_message(INITIAL, False, name=name)
    elif level == INITIAL:
        text = text.split("*")[-1]
        if text == "1":
            sessions[session_id] = PRODUCT
            msg = create_message(PRODUCT)
        elif text == "2":
            sessions[session_id] = END
            msg = create_message(END, True)
    elif level == PRODUCT:
        sessions[session_id] = QUANTITY
        msg = create_message(QUANTITY)
    elif level == QUANTITY:
        quantity = text.split("*")[-1] # validate it's a number
        sessions[session_id] = PRICE
        msg = create_message(PRICE)
    elif level == PRICE:
        unit_price = text.split("*")[-1]
        quantity = text.split("*")[-2]
        product = text.split("*")[-3]
        total_price = float(unit_price) * float(quantity)
        seshtrans[session_id] = {"product": product, "quantity": quantity, "unit_price": unit_price, "total_price": total_price}
        sessions[session_id] = CONFIRMATION
        msg = create_message(CONFIRMATION, False, product=product, quantity=quantity, unit_price=unit_price, total_price=total_price)
    elif level == CONFIRMATION:
        text = text.split("*")[-1]
        if text == "1":
            user_id = dbs.execute('SELECT id FROM user WHERE number = ?', (phone_number,)).fetchone()[0]
            product = seshtrans[session_id]["product"]
            quantity = seshtrans[session_id]["quantity"]
            unit_price = seshtrans[session_id]["unit_price"]
            total_price = seshtrans[session_id]["total_price"]
            dbs.execute('INSERT INTO transactions (user_id, product, quantity, unit_price, total_price) VALUES (?, ?, ?, ?, ?)', (user_id, product, quantity, unit_price, total_price))
            dbs.commit()
            sessions[session_id] = FINAL
            msg = create_message(FINAL, True, amount=total_price)
        else:
            dbs.rollback()
            sessions[session_id] = END
            msg = create_message(END, True)

    return msg

def create_message(type, is_last_msg = False, **kwargs):
    prefix = "END" if is_last_msg else "CON"

    if is_last_msg and "session_id" in kwargs:
        del sessions[kwargs["session_id"]]
    
    if type == EMPTY:
        msg = "Welcome to Ekan. Please type out your full name?\n"
    elif type == INITIAL:
        name = kwargs.get("name", "Unknown")
        msg =  f'Contract for {name}\nDid you sell any produce to a customer?\n1. Yes\n2. No\n'
    elif type == PRODUCT:
        msg = "What produce did you sell? (Eg. Tomatoes)\n"
    elif type == QUANTITY:
        msg = "What quantity of produce did you sell? (Eg. 10)\n"
    elif type == PRICE:
        msg = "What was the price per unit (in cedis)? (Eg. 50)\n"
    elif type == CONFIRMATION:
        msg = "Please confirm the details of the transaction\n"
        msg += f'Product: {kwargs["product"]}\n'
        msg += f'Quantity: {kwargs["quantity"]}\n'
        msg += f'Unit Price: {kwargs["unit_price"]}\n'
        msg += f'Total Price: {kwargs["total_price"]}\n'
        msg += "1. Confirm\n2. Cancel\n"
    elif type == END:
        msg = "Thank you for using our service. No further action required\n"
    elif type == FINAL:
        msg = f'Thank you for using our service. You have successfully recorded a payment of $ {kwargs["amount"]}.\n'
    else:
        msg = "Invalid input\n"
    return f'{prefix} {msg}'