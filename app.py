import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("DEALGUARD_SECRET_KEY", "change-this-secret-key-for-deployment")
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

# Uses the project's category-price reference file when it is supplied.
REFERENCE_PATH = os.path.join(BASE_DIR, "category_price_reference.csv")
if os.path.exists(REFERENCE_PATH):
    try:
        category_reference = pd.read_csv(REFERENCE_PATH)
    except Exception:
        category_reference = pd.DataFrame()
else:
    category_reference = pd.DataFrame()

DEFAULT_CATEGORIES = [
    "Electronics", "Fashion", "Home & Kitchen", "Beauty & Personal Care",
    "Books", "Sports & Fitness", "Toys & Games", "Grocery",
    "Footwear", "Accessories"
]

def get_categories():
    if not category_reference.empty and "main_category" in category_reference.columns:
        values = category_reference["main_category"].dropna().astype(str).unique().tolist()
        if values:
            return sorted(values)
    return DEFAULT_CATEGORIES

def detect_category_price(product_price, category):
    required = {"main_category", "Product_Count", "Upper_Limit"}
    if category_reference.empty or not required.issubset(category_reference.columns):
        return "Reference Data Unavailable", None
    selected = category_reference[
        category_reference["main_category"].astype(str).str.lower() == category.lower()
    ]
    if selected.empty:
        return "Category Not Found", None
    row = selected.iloc[0]
    if pd.isna(row["Product_Count"]) or float(row["Product_Count"]) < 20:
        return "Insufficient Data", None
    upper_limit = float(row["Upper_Limit"])
    if product_price > upper_limit:
        return "Unusually High Price", round(upper_limit, 2)
    return "Normal Price", round(upper_limit, 2)

def analyze_deal(actual_price, discounted_price, advertised_discount,
                 delivery_charge, category, countdown_timer="No",
                 low_stock_warning="No", hidden_charges="No"):
    calculated_discount = ((actual_price - discounted_price) / actual_price) * 100
    difference = abs(advertised_discount - calculated_discount)
    discount_status = "Match" if difference <= 2 else "Mismatch"
    warnings, penalty = [], 0

    if discount_status == "Mismatch":
        penalty += 35
        warnings.append("Advertised discount does not match the calculated discount.")

    price_status, category_limit = detect_category_price(discounted_price, category)
    if price_status == "Unusually High Price":
        penalty += 15
        warnings.append("Selling price is unusually high for this product category.")
    elif price_status == "Insufficient Data":
        warnings.append("Not enough products in this category for reliable price comparison.")
    elif price_status == "Category Not Found":
        warnings.append("Selected product category was not found in the reference data.")
    elif price_status == "Reference Data Unavailable":
        warnings.append("Category price reference file is unavailable; category comparison was skipped.")

    if countdown_timer == "Yes":
        penalty += 10
        warnings.append("A countdown timer was reported. Check whether the deadline is genuine.")
    if low_stock_warning == "Yes":
        penalty += 10
        warnings.append("A low-stock warning was reported. Check whether the stock claim is genuine.")
    if hidden_charges == "Yes":
        penalty += 15
        warnings.append("Additional charges were reportedly revealed only at checkout.")

    total_price = discounted_price + delivery_charge
    if delivery_charge > 0:
        warnings.append("Delivery charges are included in the total payable amount.")
    score = max(0, 100 - penalty)
    classification = "Legit Deal" if score >= 80 else ("Average Deal" if score >= 50 else "Suspicious Deal")
    if not warnings:
        warnings.append("No major issues were detected from the information entered.")
    return {
        "calculated_discount": round(calculated_discount, 2),
        "difference": round(difference, 2),
        "discount_status": discount_status,
        "score": score,
        "classification": classification,
        "delivery_charge": delivery_charge,
        "total_price": total_price,
        "price_status": price_status,
        "category_limit": category_limit,
        "category": category,
        "countdown_timer": countdown_timer,
        "low_stock_warning": low_stock_warning,
        "hidden_charges": hidden_charges,
        "warnings": warnings
    }

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def home():
    return render_template("index.html", categories=get_categories())

@app.route("/product")
def product():
    return render_template("product.html", categories=get_categories())

@app.route("/preview", methods=["POST"])
def preview():
    data = {
        "product_url": request.form.get("product_url", "").strip(),
        "product_name": request.form.get("product_name", "").strip(),
        "category": request.form.get("category", "").strip(),
        "actual_price": request.form.get("actual_price", "").strip(),
        "discounted_price": request.form.get("discounted_price", "").strip(),
        "advertised_discount": request.form.get("advertised_discount", "").strip(),
        "delivery_charge": request.form.get("delivery_charge", "0").strip(),
        "countdown_timer": request.form.get("countdown_timer", "No"),
        "low_stock_warning": request.form.get("low_stock_warning", "No"),
        "hidden_charges": request.form.get("hidden_charges", "No"),
    }
    image = request.files.get("product_image")
    image_filename = ""
    if image and image.filename:
        if not allowed_file(image.filename):
            flash("Please upload a JPG, PNG, WEBP or GIF image.")
            return redirect(url_for("product"))
        image_filename = secure_filename(image.filename)
        # Avoid collisions while retaining the original extension.
        import uuid
        ext = os.path.splitext(image_filename)[1].lower()
        image_filename = uuid.uuid4().hex + ext
        image.save(os.path.join(UPLOAD_DIR, image_filename))
    data["image_filename"] = image_filename
    data["image_url"] = url_for("static", filename="uploads/" + image_filename) if image_filename else None
    if not data["product_name"] or not data["category"]:
        flash("Please enter a product name and select a category.")
        return redirect(url_for("product"))
    session["pending_deal"] = data
    return render_template("preview.html", deal=data)

@app.route("/analyse", methods=["POST"])
def analyse():
    data = dict(session.get("pending_deal") or {})
    # Also accept posted fields for compatibility with direct form submissions.
    for key in ["product_url", "product_name", "category", "actual_price",
                "discounted_price", "advertised_discount", "delivery_charge",
                "countdown_timer", "low_stock_warning", "hidden_charges", "image_filename"]:
        if request.form.get(key) is not None:
            data[key] = request.form.get(key)
    try:
        product_name = str(data.get("product_name", "")).strip()
        category = str(data.get("category", "")).strip()
        actual_price = float(data.get("actual_price", 0))
        discounted_price = float(data.get("discounted_price", 0))
        advertised_discount = float(data.get("advertised_discount", 0))
        delivery_charge = float(data.get("delivery_charge", 0))
        countdown = data.get("countdown_timer", "No")
        low_stock = data.get("low_stock_warning", "No")
        hidden = data.get("hidden_charges", "No")
        if not product_name or not category:
            raise ValueError("Please enter product name and category.")
        if actual_price <= 0 or discounted_price <= 0:
            raise ValueError("Prices must be greater than zero.")
        if discounted_price > actual_price:
            raise ValueError("Selling price cannot exceed original price.")
        if not 0 <= advertised_discount <= 100:
            raise ValueError("Advertised discount must be between 0 and 100.")
        if delivery_charge < 0:
            raise ValueError("Delivery charge cannot be negative.")
    except (ValueError, TypeError) as exc:
        flash(str(exc) or "Please enter valid numerical product details.")
        return redirect(url_for("product"))

    result = analyze_deal(actual_price, discounted_price, advertised_discount,
                          delivery_charge, category, countdown, low_stock, hidden)
    deal = {
        "product_name": product_name, "product_url": data.get("product_url", ""),
        "category": category, "actual_price": actual_price,
        "discounted_price": discounted_price, "advertised_discount": advertised_discount,
        "delivery_charge": delivery_charge, "image_url": data.get("image_url"),
        "image_filename": data.get("image_filename", ""), "result": result
    }
    session["deal_data"] = deal
    return render_template("verification.html", deal=deal)

@app.route("/dark-patterns")
def dark_patterns():
    deal = session.get("deal_data")
    if not deal:
        flash("Please analyse a product first.")
        return redirect(url_for("product"))
    return render_template("dark_patterns.html", deal=deal)

@app.route("/final-report")
def final_report():
    deal = session.get("deal_data")
    if not deal:
        flash("Please analyse a product first.")
        return redirect(url_for("product"))
    return render_template("final_report.html", deal=deal)

@app.route("/about")
def about():
    return render_template("about.html")

@app.errorhandler(413)
def too_large(_error):
    flash("Image is too large. Please upload an image smaller than 5 MB.")
    return redirect(url_for("product"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
