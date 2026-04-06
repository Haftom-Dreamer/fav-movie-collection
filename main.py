from flask import Flask, render_template, redirect, url_for, request, flash
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from wtforms import StringField, SubmitField, PasswordField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import os
from datetime import datetime, date
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Float, DateTime, ForeignKey, Date

TMDB_API_KEY = "f319b185cd1af98f98b55a81304dfe9b"

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
Bootstrap(app)
db_path = os.path.abspath("favorite-movies.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- DB Setup ---
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
db.init_app(app)

# --- Login Manager ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# =====================
# --- DB Models ---
# =====================

AVATAR_COLORS = ["#6c63ff", "#ff6584", "#43b89c", "#f5a623", "#4ecdc4", "#c56ef3"]

class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    avatar_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#6c63ff")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    movies: Mapped[list["Movie"]] = relationship("Movie", back_populates="owner", cascade="all, delete-orphan")
    books: Mapped[list["Book"]] = relationship("Book", back_populates="owner", cascade="all, delete-orphan")

class Movie(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    tmdb_id: Mapped[str] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    year: Mapped[str] = mapped_column(String(10), nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    review: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    img_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="to_watch")  # "watched" | "to_watch"
    genre: Mapped[str] = mapped_column(String(200), nullable=True, default="")
    date_added: Mapped[date] = mapped_column(Date, default=date.today)
    date_watched: Mapped[date] = mapped_column(Date, nullable=True)
    owner: Mapped["User"] = relationship("User", back_populates="movies")

class Book(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    google_id: Mapped[str] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    author: Mapped[str] = mapped_column(String(250), nullable=False, default="Unknown")
    year: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    review: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    img_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="to_read")  # "read" | "to_read"
    genre: Mapped[str] = mapped_column(String(200), nullable=True, default="")
    date_added: Mapped[date] = mapped_column(Date, default=date.today)
    date_read: Mapped[date] = mapped_column(Date, nullable=True)
    owner: Mapped["User"] = relationship("User", back_populates="books")


with app.app_context():
    db.create_all()


# =====================
# --- Auth Routes ---
# =====================

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    class RegisterForm(FlaskForm):
        username = StringField("Username", validators=[DataRequired(), Length(3, 80)])
        email = StringField("Email", validators=[DataRequired(), Email()])
        password = PasswordField("Password", validators=[DataRequired(), Length(6)])
        confirm = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password")])
        submit = SubmitField("Create Account")
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash("Email already registered. Please log in.", "error")
            return redirect(url_for("login"))
        if User.query.filter_by(username=form.username.data).first():
            flash("Username already taken.", "error")
            return redirect(url_for("register"))
        import random
        color = random.choice(AVATAR_COLORS)
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            avatar_color=color
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome! Your account has been created.", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    class LoginForm(FlaskForm):
        email = StringField("Email", validators=[DataRequired(), Email()])
        password = PasswordField("Password", validators=[DataRequired()])
        submit = SubmitField("Sign In")
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("landing"))


# =====================
# --- Core Routes ---
# =====================

@app.route("/")
def landing():
    return render_template("index.html")


@app.route("/dashboard")
@login_required
def dashboard():
    movies = Movie.query.filter_by(user_id=current_user.id).all()
    books = Book.query.filter_by(user_id=current_user.id).all()
    watched = [m for m in movies if m.status == "watched"]
    to_watch = [m for m in movies if m.status == "to_watch"]
    read = [b for b in books if b.status == "read"]
    to_read = [b for b in books if b.status == "to_read"]

    # Monthly stats (current month)
    today = date.today()
    movies_this_month = [m for m in watched if m.date_watched and
                         m.date_watched.month == today.month and m.date_watched.year == today.year]
    books_this_month = [b for b in read if b.date_read and
                        b.date_read.month == today.month and b.date_read.year == today.year]

    # Recent activity (last 5 items combined, sorted by date_added)
    all_items = []
    for m in movies:
        all_items.append({"type": "movie", "item": m, "date": m.date_added})
    for b in books:
        all_items.append({"type": "book", "item": b, "date": b.date_added})
    all_items.sort(key=lambda x: x["date"] or date.min, reverse=True)
    recent = all_items[:6]

    return render_template("dashboard.html",
        watched_count=len(watched),
        to_watch_count=len(to_watch),
        read_count=len(read),
        to_read_count=len(to_read),
        movies_this_month=len(movies_this_month),
        books_this_month=len(books_this_month),
        recent=recent,
        avg_movie_rating=round(sum(m.rating for m in watched if m.rating) / max(len(watched), 1), 1),
        avg_book_rating=round(sum(b.rating for b in read if b.rating) / max(len(read), 1), 1),
    )


@app.route("/collection")
@login_required
def collection():
    tab = request.args.get("tab", "movies")
    status = request.args.get("status", "all")
    
    movie_q = Movie.query.filter_by(user_id=current_user.id)
    book_q = Book.query.filter_by(user_id=current_user.id)
    
    if status == "watched":
        movie_q = movie_q.filter_by(status="watched")
    elif status == "to_watch":
        movie_q = movie_q.filter_by(status="to_watch")

    if status == "read":
        book_q = book_q.filter_by(status="read")
    elif status == "to_read":
        book_q = book_q.filter_by(status="to_read")
    
    movies = movie_q.order_by(Movie.date_added.desc()).all()
    books = book_q.order_by(Book.date_added.desc()).all()
    return render_template("collection.html", movies=movies, books=books, tab=tab, status=status)


@app.route("/discover")
@login_required
def discover():
    # TMDB Trending Movies
    trending_movies = []
    try:
        r = requests.get(
            "https://api.themoviedb.org/3/trending/movie/week",
            params={"api_key": TMDB_API_KEY}
        )
        data = r.json()
        for item in data.get("results", [])[:12]:
            trending_movies.append({
                "tmdb_id": item["id"],
                "title": item.get("title", "Unknown"),
                "year": (item.get("release_date") or "")[:4],
                "img_url": f"https://image.tmdb.org/t/p/w300{item.get('poster_path', '')}",
                "rating": item.get("vote_average", 0),
                "overview": item.get("overview", "")[:200],
            })
    except Exception:
        pass

    # Google Books "bestsellers" / popular
    trending_books = []
    try:
        r = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": "subject:fiction&orderBy=relevance", "maxResults": 12, "printType": "books"}
        )
        data = r.json()
        for item in data.get("items", []):
            vol = item.get("volumeInfo", {})
            thumb = ""
            if "imageLinks" in vol:
                thumb = vol["imageLinks"].get("thumbnail", "").replace("http://", "https://")
            trending_books.append({
                "google_id": item.get("id"),
                "title": vol.get("title", "Unknown"),
                "author": ", ".join(vol.get("authors", ["Unknown"])),
                "year": (vol.get("publishedDate") or "")[:4],
                "img_url": thumb,
                "overview": vol.get("description", "")[:200],
            })
    except Exception:
        pass

    return render_template("discover.html", trending_movies=trending_movies, trending_books=trending_books)


# =====================
# --- Movie Routes ---
# =====================

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    class AddForm(FlaskForm):
        title = StringField("Movie Title", validators=[DataRequired()])
        submit = SubmitField("Search Movie")
    form = AddForm()
    if form.validate_on_submit():
        return redirect(url_for("find", title=form.title.data))
    return render_template("add.html", form=form, item_type="Movie")


@app.route("/find")
@login_required
def find():
    title = request.args.get("title")
    if not title:
        return redirect(url_for("add"))
    r = requests.get("https://api.themoviedb.org/3/search/movie",
                     params={"api_key": TMDB_API_KEY, "query": title})
    data = r.json()
    return render_template("select.html", items=data.get("results", []), item_type="Movie")


@app.route("/select")
@login_required
def select():
    tmdb_id = request.args.get("id")
    if not tmdb_id:
        return redirect(url_for("add"))
    r = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}",
                     params={"api_key": TMDB_API_KEY})
    d = r.json()
    genres = ", ".join([g["name"] for g in d.get("genres", [])])
    new_movie = Movie(
        user_id=current_user.id,
        tmdb_id=str(tmdb_id),
        title=d.get("title", "Unknown"),
        year=(d.get("release_date") or "")[:4],
        rating=0.0,
        description=d.get("overview", "")[:1000],
        genre=genres,
        img_url=f"https://image.tmdb.org/t/p/w500{d.get('poster_path', '')}",
        status="to_watch",
    )
    db.session.add(new_movie)
    db.session.commit()
    return redirect(url_for("edit", movie_id=new_movie.id))


@app.route("/edit/<int:movie_id>", methods=["GET", "POST"])
@login_required
def edit(movie_id):
    movie = db.session.get(Movie, movie_id)
    if not movie or movie.user_id != current_user.id:
        return redirect(url_for("collection"))
    class EditForm(FlaskForm):
        rating = StringField("Your Rating (0–10)")
        review = StringField("Your Review")
        status = SelectField("Status", choices=[("to_watch", "🕐 To Watch"), ("watched", "✅ Watched")])
        submit = SubmitField("Save")
    form = EditForm()
    if form.validate_on_submit():
        try:
            movie.rating = float(form.rating.data or 0)
        except ValueError:
            movie.rating = 0.0
        movie.review = form.review.data
        movie.status = form.status.data
        if form.status.data == "watched" and not movie.date_watched:
            movie.date_watched = date.today()
        db.session.commit()
        return redirect(url_for("collection", tab="movies"))
    form.rating.data = str(movie.rating)
    form.review.data = movie.review
    form.status.data = movie.status
    return render_template("edit.html", item=movie, form=form, item_type="Movie")


@app.route("/delete/<int:movie_id>")
@login_required
def delete(movie_id):
    movie = db.session.get(Movie, movie_id)
    if movie and movie.user_id == current_user.id:
        db.session.delete(movie)
        db.session.commit()
    return redirect(url_for("collection", tab="movies"))


# Quick-add from discover page
@app.route("/quick_add_movie")
@login_required
def quick_add_movie():
    tmdb_id = request.args.get("id")
    return redirect(url_for("select", id=tmdb_id))


# =====================
# --- Book Routes ---
# =====================

@app.route("/add_book", methods=["GET", "POST"])
@login_required
def add_book():
    class AddBookForm(FlaskForm):
        title = StringField("Book Title", validators=[DataRequired()])
        submit = SubmitField("Search Book")
    form = AddBookForm()
    if form.validate_on_submit():
        return redirect(url_for("find_book", title=form.title.data))
    return render_template("add.html", form=form, item_type="Book")


@app.route("/find_book")
@login_required
def find_book():
    title = request.args.get("title")
    if not title:
        return redirect(url_for("add_book"))
    r = requests.get("https://www.googleapis.com/books/v1/volumes",
                     params={"q": title, "maxResults": 10})
    data = r.json()
    items = []
    for item in data.get("items", []):
        vol = item.get("volumeInfo", {})
        thumb = ""
        if "imageLinks" in vol:
            thumb = vol["imageLinks"].get("thumbnail", "").replace("http://", "https://")
        items.append({
            "id": item.get("id"),
            "title": vol.get("title", "Unknown"),
            "release_date": vol.get("publishedDate", ""),
            "poster_path": None,
            "thumb": thumb,
        })
    return render_template("select.html", items=items, item_type="Book")


@app.route("/select_book")
@login_required
def select_book():
    book_id = request.args.get("id")
    if not book_id:
        return redirect(url_for("add_book"))
    r = requests.get(f"https://www.googleapis.com/books/v1/volumes/{book_id}")
    data = r.json()
    vol = data.get("volumeInfo", {})
    year = (vol.get("publishedDate") or "")[:4]
    authors = ", ".join(vol.get("authors", ["Unknown"]))
    thumb = ""
    if "imageLinks" in vol:
        thumb = vol["imageLinks"].get("thumbnail", "").replace("http://", "https://")
    categories = ", ".join(vol.get("categories", []))
    new_book = Book(
        user_id=current_user.id,
        google_id=book_id,
        title=vol.get("title", "Unknown"),
        author=authors,
        year=year,
        rating=0.0,
        description=vol.get("description", "")[:1000],
        genre=categories,
        img_url=thumb,
        status="to_read",
    )
    db.session.add(new_book)
    db.session.commit()
    return redirect(url_for("edit_book", book_id=new_book.id))


@app.route("/edit_book/<int:book_id>", methods=["GET", "POST"])
@login_required
def edit_book(book_id):
    book = db.session.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        return redirect(url_for("collection"))
    class EditForm(FlaskForm):
        rating = StringField("Your Rating (0–10)")
        review = StringField("Your Review")
        status = SelectField("Status", choices=[("to_read", "📖 To Read"), ("read", "✅ Read")])
        submit = SubmitField("Save")
    form = EditForm()
    if form.validate_on_submit():
        try:
            book.rating = float(form.rating.data or 0)
        except ValueError:
            book.rating = 0.0
        book.review = form.review.data
        book.status = form.status.data
        if form.status.data == "read" and not book.date_read:
            book.date_read = date.today()
        db.session.commit()
        return redirect(url_for("collection", tab="books"))
    form.rating.data = str(book.rating)
    form.review.data = book.review
    form.status.data = book.status
    return render_template("edit.html", item=book, form=form, item_type="Book")


@app.route("/delete_book/<int:book_id>")
@login_required
def delete_book(book_id):
    book = db.session.get(Book, book_id)
    if book and book.user_id == current_user.id:
        db.session.delete(book)
        db.session.commit()
    return redirect(url_for("collection", tab="books"))


if __name__ == "__main__":
    app.run(debug=True)
