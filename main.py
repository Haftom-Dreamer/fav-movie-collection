from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from wtforms import StringField, SubmitField, PasswordField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import os
from datetime import datetime, date, timedelta
from collections import Counter, defaultdict
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Float, DateTime, ForeignKey, Date

TMDB_API_KEY = "f319b185cd1af98f98b55a81304dfe9b"

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7Y0sKR6b'
Bootstrap(app)
db_path = os.path.abspath("favorite-movies.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

AVATAR_COLORS = ["#6c63ff", "#ff6584", "#43b89c", "#f5a623", "#4ecdc4", "#c56ef3"]

# =====================
# --- DB Models ---
# =====================

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
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="to_watch")
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
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="to_read")
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
    read_books = [b for b in books if b.status == "read"]
    to_read = [b for b in books if b.status == "to_read"]

    today = date.today()

    # --- Monthly stats (current month) ---
    movies_this_month = [m for m in watched if m.date_watched and
                         m.date_watched.month == today.month and m.date_watched.year == today.year]
    books_this_month = [b for b in read_books if b.date_read and
                        b.date_read.month == today.month and b.date_read.year == today.year]

    # --- Streak (consecutive days with activity) ---
    activity_dates = set()
    for m in watched:
        if m.date_watched:
            activity_dates.add(m.date_watched)
    for b in read_books:
        if b.date_read:
            activity_dates.add(b.date_read)
    streak = 0
    check_date = today
    while check_date in activity_dates:
        streak += 1
        check_date -= timedelta(days=1)

    # --- Recent activity ---
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
        read_count=len(read_books),
        to_read_count=len(to_read),
        movies_this_month=len(movies_this_month),
        books_this_month=len(books_this_month),
        recent=recent,
        avg_movie_rating=round(sum(m.rating for m in watched if m.rating) / max(len(watched), 1), 1),
        streak=streak
    )

@app.route("/analytics")
@login_required
def analytics():
    movies = current_user.movies
    books = current_user.books
    watched = [m for m in movies if m.status == "watched"]
    to_watch = [m for m in movies if m.status == "to_watch"]
    read_books = [b for b in books if b.status == "read"]
    
    today = date.today()

    # --- Weekly activity (last 7 days) ---
    week_labels = []
    week_movies = []
    week_books = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        week_labels.append(d.strftime("%a"))
        week_movies.append(sum(1 for m in watched if m.date_watched == d))
        week_books.append(sum(1 for b in read_books if b.date_read == d))

    # --- Monthly chart (this year) ---
    month_labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    month_movies = [0]*12
    month_books = [0]*12
    for m in watched:
        if m.date_watched and m.date_watched.year == today.year:
            month_movies[m.date_watched.month - 1] += 1
    for b in read_books:
        if b.date_read and b.date_read.year == today.year:
            month_books[b.date_read.month - 1] += 1

    # --- Genre breakdown ---
    genre_counts = Counter()
    for m in watched:
        if m.genre:
            for g in m.genre.split(","):
                genre_counts[g.strip()] += 1
    for b in read_books:
        if b.genre:
            for g in b.genre.split(","):
                genre_counts[g.strip()] += 1
    top_genres = genre_counts.most_common(6)

    # --- Completion rate ---
    total_movies = len(movies)
    completion_pct = round(len(watched) / total_movies * 100) if total_movies else 0

    week_max = max((week_movies[i] + week_books[i] for i in range(7)), default=0) or 1
    month_max = max((month_movies[i] + month_books[i] for i in range(12)), default=0) or 1

    return render_template("analytics.html",
        watched_count=len(watched),
        to_watch_count=len(to_watch),
        week_labels=week_labels,
        week_movies=week_movies,
        week_books=week_books,
        week_max=week_max,
        month_labels=month_labels,
        month_movies=month_movies,
        month_books=month_books,
        month_max=month_max,
        top_genres=top_genres,
        completion_pct=completion_pct,
    )


@app.route("/collection")
@login_required
def collection():
    tab = request.args.get("tab", "movies")
    status = request.args.get("status", "all")
    sort = request.args.get("sort", "newest")

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

    if sort == "rating":
        movie_q = movie_q.order_by(Movie.rating.desc())
        book_q = book_q.order_by(Book.rating.desc())
    elif sort == "title":
        movie_q = movie_q.order_by(Movie.title)
        book_q = book_q.order_by(Book.title)
    else:  # newest
        movie_q = movie_q.order_by(Movie.date_added.desc())
        book_q = book_q.order_by(Book.date_added.desc())

    movies = movie_q.all()
    books = book_q.all()
    return render_template("collection.html", movies=movies, books=books,
                           tab=tab, status=status, sort=sort)


# =====================
# --- Discover (Personalized + Filtered) ---
# =====================

def _get_user_collection_ids():
    movie_tmdb_ids = {m.tmdb_id for m in Movie.query.filter_by(user_id=current_user.id).all() if m.tmdb_id}
    book_google_ids = {b.google_id for b in Book.query.filter_by(user_id=current_user.id).all() if b.google_id}
    return movie_tmdb_ids, book_google_ids


@app.route("/discover")
@login_required
def discover():
    import random
    movie_in_collection, book_in_collection = _get_user_collection_ids()
    refresh = request.args.get('refresh', type=int, default=0)
    page_offset = random.randint(1, 4) if refresh else 1

    # -- Personalized movie recommendations --
    user_movies = Movie.query.filter_by(user_id=current_user.id, status="watched").all()
    genre_ids = set()
    for m in user_movies:
        if m.tmdb_id:
            try:
                r = requests.get(f"https://api.themoviedb.org/3/movie/{m.tmdb_id}",
                                 params={"api_key": TMDB_API_KEY}, timeout=4)
                for g in r.json().get("genres", []):
                    genre_ids.add(str(g["id"]))
                if len(genre_ids) >= 6:
                    break
            except Exception:
                pass

    if genre_ids and refresh:
        genre_ids = set(random.sample(list(genre_ids), min(3, len(genre_ids))))

    recommended_movies = []
    is_personalized_movies = bool(genre_ids)
    if is_personalized_movies:
        try:
            params = {"api_key": TMDB_API_KEY, "sort_by": "popularity.desc", "page": page_offset}
            params["with_genres"] = ",".join(list(genre_ids)[:3])
            r = requests.get("https://api.themoviedb.org/3/discover/movie", params=params, timeout=6)
            for item in r.json().get("results", []):
                tid = str(item["id"])
                if tid in movie_in_collection: continue
                if item.get("poster_path"):
                    recommended_movies.append({
                        "tmdb_id": tid, "title": item.get("title", ""),
                        "year": (item.get("release_date") or "")[:4],
                        "img_url": f"https://image.tmdb.org/t/p/w300{item['poster_path']}",
                        "rating": round(item.get("vote_average", 0), 1),
                        "overview": (item.get("overview") or "")[:200]
                    })
                if len(recommended_movies) >= 12: break
        except Exception: pass

    trending_movies = []
    try:
        tparams = {"api_key": TMDB_API_KEY, "sort_by": "popularity.desc", "page": page_offset}
        r = requests.get("https://api.themoviedb.org/3/discover/movie", params=tparams, timeout=6)
        for item in r.json().get("results", []):
            tid = str(item["id"])
            if tid in movie_in_collection: continue
            if item.get("poster_path"):
                trending_movies.append({
                    "tmdb_id": tid, "title": item.get("title", ""),
                    "year": (item.get("release_date") or "")[:4],
                    "img_url": f"https://image.tmdb.org/t/p/w300{item['poster_path']}",
                    "rating": round(item.get("vote_average", 0), 1),
                    "overview": (item.get("overview") or "")[:200]
                })
            if len(trending_movies) >= 12: break
    except Exception: pass

    # -- Personalized book recommendations --
    user_books = Book.query.filter_by(user_id=current_user.id, status="read").all()
    book_subjects = []
    for b in user_books:
        if b.genre:
            book_subjects += [g.strip().lower() for g in b.genre.split(",") if g.strip()]
    if book_subjects and refresh:
        random.shuffle(book_subjects)
        
    book_query = "+".join(book_subjects[:2]) if book_subjects else ""
    is_personalized_books = bool(book_query)

    recommended_books = []
    if is_personalized_books:
        try:
            r = requests.get("https://www.googleapis.com/books/v1/volumes",
                             params={"q": f"subject:{book_query}", "maxResults": 20,
                                     "orderBy": "relevance", "printType": "books", "startIndex": (page_offset-1)*15}, timeout=6)
            for item in r.json().get("items", []):
                gid = item.get("id")
                if gid in book_in_collection: continue
                vol = item.get("volumeInfo", {})
                thumb = vol.get("imageLinks", {}).get("thumbnail", "").replace("http://", "https://")
                if not thumb: continue
                recommended_books.append({
                    "google_id": gid, "title": vol.get("title", ""),
                    "author": ", ".join(vol.get("authors", ["Unknown"])),
                    "year": (vol.get("publishedDate") or "")[:4],
                    "img_url": thumb, "overview": (vol.get("description") or "")[:200]
                })
                if len(recommended_books) >= 12: break
        except Exception: pass

    trending_books = []
    try:
        tr = requests.get("https://www.googleapis.com/books/v1/volumes",
                         params={"q": "subject:fiction", "maxResults": 20,
                                 "orderBy": "newest", "printType": "books", "startIndex": (page_offset-1)*15}, timeout=6)
        for item in tr.json().get("items", []):
            gid = item.get("id")
            if gid in book_in_collection: continue
            vol = item.get("volumeInfo", {})
            thumb = vol.get("imageLinks", {}).get("thumbnail", "").replace("http://", "https://")
            if not thumb: continue
            trending_books.append({
                "google_id": gid, "title": vol.get("title", ""),
                "author": ", ".join(vol.get("authors", ["Unknown"])),
                "year": (vol.get("publishedDate") or "")[:4],
                "img_url": thumb, "overview": (vol.get("description") or "")[:200]
            })
            if len(trending_books) >= 12: break
    except Exception: pass

    return render_template("discover.html",
        recommended_movies=recommended_movies,
        trending_movies=trending_movies,
        recommended_books=recommended_books,
        trending_books=trending_books,
        is_personalized_movies=is_personalized_movies,
        is_personalized_books=is_personalized_books,
    )


# =====================
# --- Preview Routes (JSON) ---
# =====================

@app.route("/movie_preview/<int:tmdb_id>")
@login_required
def movie_preview(tmdb_id):
    try:
        r = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}",
                         params={"api_key": TMDB_API_KEY, "append_to_response": "credits"}, timeout=6)
        d = r.json()
        cast = [c["name"] for c in d.get("credits", {}).get("cast", [])[:5]]
        genres = [g["name"] for g in d.get("genres", [])]
        return jsonify({
            "title": d.get("title", ""),
            "year": (d.get("release_date") or "")[:4],
            "overview": d.get("overview", ""),
            "poster": f"https://image.tmdb.org/t/p/w300{d.get('poster_path', '')}",
            "rating": round(d.get("vote_average", 0), 1),
            "genres": ", ".join(genres),
            "cast": ", ".join(cast),
            "runtime": d.get("runtime", ""),
            "tmdb_id": tmdb_id,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/book_preview/<book_id>")
@login_required
def book_preview(book_id):
    try:
        r = requests.get(f"https://www.googleapis.com/books/v1/volumes/{book_id}", timeout=6)
        data = r.json()
        vol = data.get("volumeInfo", {})
        thumb = ""
        if "imageLinks" in vol:
            thumb = vol["imageLinks"].get("thumbnail", "").replace("http://", "https://")
        return jsonify({
            "title": vol.get("title", ""),
            "author": ", ".join(vol.get("authors", ["Unknown"])),
            "year": (vol.get("publishedDate") or "")[:4],
            "overview": (vol.get("description") or "")[:600],
            "poster": thumb,
            "genres": ", ".join(vol.get("categories", [])),
            "pages": vol.get("pageCount", ""),
            "google_id": book_id,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =====================
# --- Quick Add Routes ---
# =====================

@app.route("/quick_add_movie")
@login_required
def quick_add_movie():
    tmdb_id = request.args.get("id")
    status = request.args.get("status", "to_watch")
    if not tmdb_id:
        return redirect(url_for("discover"))

    # Don't add duplicates
    existing = Movie.query.filter_by(user_id=current_user.id, tmdb_id=str(tmdb_id)).first()
    if existing:
        flash(f'"{existing.title}" is already in your collection.', "error")
        return redirect(url_for("discover"))

    try:
        r = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}",
                         params={"api_key": TMDB_API_KEY}, timeout=6)
        d = r.json()
        genres = ", ".join([g["name"] for g in d.get("genres", [])])
        new_movie = Movie(
            user_id=current_user.id,
            tmdb_id=str(tmdb_id),
            title=d.get("title", "Unknown"),
            year=(d.get("release_date") or "")[:4],
            rating=0.0,
            description=(d.get("overview") or "")[:1000],
            genre=genres,
            img_url=f"https://image.tmdb.org/t/p/w500{d.get('poster_path', '')}",
            status=status,
            date_watched=date.today() if status == "watched" else None,
        )
        db.session.add(new_movie)
        db.session.commit()
        flash(f'"{new_movie.title}" added to your collection!', "success")
    except Exception as e:
        flash(f"Could not add movie: {str(e)}", "error")

    return redirect(url_for("discover"))


@app.route("/quick_add_book")
@login_required
def quick_add_book():
    google_id = request.args.get("id")
    status = request.args.get("status", "to_read")
    if not google_id:
        return redirect(url_for("discover"))

    existing = Book.query.filter_by(user_id=current_user.id, google_id=google_id).first()
    if existing:
        flash(f'"{existing.title}" is already in your collection.', "error")
        return redirect(url_for("discover"))

    try:
        r = requests.get(f"https://www.googleapis.com/books/v1/volumes/{google_id}", timeout=6)
        data = r.json()
        vol = data.get("volumeInfo", {})
        thumb = ""
        if "imageLinks" in vol:
            thumb = vol["imageLinks"].get("thumbnail", "").replace("http://", "https://")
        new_book = Book(
            user_id=current_user.id,
            google_id=google_id,
            title=vol.get("title", "Unknown"),
            author=", ".join(vol.get("authors", ["Unknown"])),
            year=(vol.get("publishedDate") or "")[:4],
            rating=0.0,
            description=(vol.get("description") or "")[:1000],
            genre=", ".join(vol.get("categories", [])),
            img_url=thumb,
            status=status,
            date_read=date.today() if status == "read" else None,
        )
        db.session.add(new_book)
        db.session.commit()
        flash(f'"{new_book.title}" added to your collection!', "success")
    except Exception as e:
        flash(f"Could not add book: {str(e)}", "error")

    return redirect(url_for("discover"))


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
    return render_template("select.html", items=data.get("results", []), item_type="Movie", query=title)


@app.route("/select")
@login_required
def select():
    tmdb_id = request.args.get("id")
    status = request.args.get("status", "to_watch")
    if not tmdb_id:
        return redirect(url_for("add"))

    existing = Movie.query.filter_by(user_id=current_user.id, tmdb_id=str(tmdb_id)).first()
    if existing:
        flash(f'"{existing.title}" is already in your collection.', "error")
        return redirect(url_for("collection", tab="movies"))

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
        description=(d.get("overview") or "")[:1000],
        genre=genres,
        img_url=f"https://image.tmdb.org/t/p/w500{d.get('poster_path', '')}",
        status=status,
        date_watched=date.today() if status == "watched" else None,
    )
    db.session.add(new_movie)
    db.session.commit()
    if status == "to_watch":
        flash(f'"{new_movie.title}" added to your watchlist!', "success")
        return redirect(url_for("collection", tab="movies"))
    return redirect(url_for("edit", movie_id=new_movie.id))


@app.route("/edit/<int:movie_id>", methods=["GET", "POST"])
@login_required
def edit(movie_id):
    movie = db.session.get(Movie, movie_id)
    if not movie or movie.user_id != current_user.id:
        return redirect(url_for("collection"))
    class EditForm(FlaskForm):
        title = StringField("Title", validators=[DataRequired()])
        rating = StringField("Your Rating (0–10)")
        review = TextAreaField("Your Review")
        description = TextAreaField("Synopsis")
        status = SelectField("Status", choices=[("to_watch", "🕐 To Watch"), ("watched", "✅ Watched")])
        submit = SubmitField("Save")
    form = EditForm()
    if form.validate_on_submit():
        movie.title = form.title.data
        try:
            movie.rating = float(form.rating.data or 0)
        except ValueError:
            movie.rating = 0.0
        movie.review = form.review.data
        movie.description = form.description.data
        movie.status = form.status.data
        if form.status.data == "watched" and not movie.date_watched:
            movie.date_watched = date.today()
        db.session.commit()
        flash("Saved!", "success")
        return redirect(url_for("collection", tab="movies"))
    form.title.data = movie.title
    form.rating.data = str(movie.rating)
    form.review.data = movie.review
    form.description.data = movie.description
    form.status.data = movie.status
    return render_template("edit.html", item=movie, form=form, item_type="Movie")


@app.route("/delete/<int:movie_id>")
@login_required
def delete(movie_id):
    movie = db.session.get(Movie, movie_id)
    if movie and movie.user_id == current_user.id:
        db.session.delete(movie)
        db.session.commit()
        flash("Movie removed.", "success")
    return redirect(url_for("collection", tab="movies"))


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
    try:
        r = requests.get("https://www.googleapis.com/books/v1/volumes",
                         params={"q": title, "maxResults": 12}, timeout=8)
        data = r.json()
    except Exception:
        flash("Could not reach Google Books API. Please try again.", "error")
        return redirect(url_for("add_book"))

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
            "author": ", ".join(vol.get("authors", ["Unknown"])),
        })
    return render_template("select.html", items=items, item_type="Book", query=title)


@app.route("/select_book")
@login_required
def select_book():
    book_id = request.args.get("id")
    status = request.args.get("status", "to_read")
    if not book_id:
        return redirect(url_for("add_book"))

    existing = Book.query.filter_by(user_id=current_user.id, google_id=book_id).first()
    if existing:
        flash(f'"{existing.title}" is already in your collection.', "error")
        return redirect(url_for("collection", tab="books"))

    try:
        r = requests.get(f"https://www.googleapis.com/books/v1/volumes/{book_id}", timeout=8)
        data = r.json()
    except Exception:
        flash("Could not fetch book details. Please try again.", "error")
        return redirect(url_for("add_book"))

    vol = data.get("volumeInfo", {})
    if not vol:
        flash("Book not found. Please try again.", "error")
        return redirect(url_for("add_book"))

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
        description=(vol.get("description") or "")[:1000],
        genre=categories,
        img_url=thumb,
        status=status,
        date_read=date.today() if status == "read" else None,
    )
    db.session.add(new_book)
    db.session.commit()

    if status == "to_read":
        flash(f'"{new_book.title}" added to your reading list!', "success")
        return redirect(url_for("collection", tab="books"))
    return redirect(url_for("edit_book", book_id=new_book.id))


@app.route("/edit_book/<int:book_id>", methods=["GET", "POST"])
@login_required
def edit_book(book_id):
    book = db.session.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        return redirect(url_for("collection"))
    class EditForm(FlaskForm):
        title = StringField("Title", validators=[DataRequired()])
        rating = StringField("Your Rating (0–10)")
        review = TextAreaField("Your Review")
        description = TextAreaField("Synopsis")
        status = SelectField("Status", choices=[("to_read", "📖 To Read"), ("read", "✅ Read")])
        submit = SubmitField("Save")
    form = EditForm()
    if form.validate_on_submit():
        book.title = form.title.data
        try:
            book.rating = float(form.rating.data or 0)
        except ValueError:
            book.rating = 0.0
        book.review = form.review.data
        book.description = form.description.data
        book.status = form.status.data
        if form.status.data == "read" and not book.date_read:
            book.date_read = date.today()
        db.session.commit()
        flash("Saved!", "success")
        return redirect(url_for("collection", tab="books"))
    form.title.data = book.title
    form.rating.data = str(book.rating)
    form.review.data = book.review
    form.description.data = book.description
    form.status.data = book.status
    return render_template("edit.html", item=book, form=form, item_type="Book")


@app.route("/delete_book/<int:book_id>")
@login_required
def delete_book(book_id):
    book = db.session.get(Book, book_id)
    if book and book.user_id == current_user.id:
        db.session.delete(book)
        db.session.commit()
        flash("Book removed.", "success")
    return redirect(url_for("collection", tab="books"))

@app.route("/api/search_movie")
@login_required
def api_search_movie():
    query = request.args.get("q", "")
    if not query:
        return jsonify([])
    try:
        r = requests.get("https://api.themoviedb.org/3/search/movie",
                         params={"api_key": TMDB_API_KEY, "query": query}, timeout=3)
        results = [{"id": i["id"], "title": i.get("title", ""), "year": (i.get("release_date") or "")[:4]}
                   for i in r.json().get("results", [])[:5]]
        return jsonify(results)
    except:
        return jsonify([])

@app.route("/api/search_book")
@login_required
def api_search_book():
    query = request.args.get("q", "")
    if not query:
        return jsonify([])
    try:
        r = requests.get("https://www.googleapis.com/books/v1/volumes",
                         params={"q": query, "maxResults": 5}, timeout=3)
        results = [{"id": i.get("id"), "title": i.get("volumeInfo", {}).get("title", ""),
                    "year": (i.get("volumeInfo", {}).get("publishedDate") or "")[:4]}
                   for i in r.json().get("items", [])]
        return jsonify(results)
    except:
        return jsonify([])

if __name__ == "__main__":
    app.run(debug=True)
