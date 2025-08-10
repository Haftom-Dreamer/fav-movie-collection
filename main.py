from flask import Flask, render_template, redirect, url_for, request
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
import requests
import os
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float

TMDB_api_key = "f319b185cd1af98f98b55a81304dfe9b"


app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
Bootstrap(app)
db_path = os.path.abspath("favorite-movies.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- SQLAlchemy Setup ---
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
db.init_app(app)

# --- Model ---
class Movie(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[str] = mapped_column(String(100), nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    ranking: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    review: Mapped[str] = mapped_column(String(500), nullable=False)
    img_url: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)



# --- Create DB ---
with app.app_context():
    db.create_all()
    

@app.route("/")
def landing():
    return render_template("index.html")

@app.route("/collection")
def collection():
    movies = db.session.query(Movie).order_by(Movie.ranking).all()
    return render_template("movie.html", movies=movies)

@app.route("/add", methods=["GET", "POST"])
def add():
    class AddForm(FlaskForm):
        title = StringField("Movie Title", validators=[DataRequired()])
        submit = SubmitField("Search Movie")

    form = AddForm()

    if form.validate_on_submit():
        return redirect(url_for('find', title=form.title.data))

    return render_template("add.html", form=form)


@app.route("/edit/<int:movie_id>", methods=["GET", "POST"])
def edit(movie_id):
    class EditForm(FlaskForm):
        rating = StringField("New Rating")
        review = StringField("New Review")
        submit = SubmitField("Update")

    form = EditForm()
    movie = db.session.get(Movie, movie_id)

    if form.validate_on_submit():
        movie.rating = float(form.rating.data)
        movie.review = form.review.data
        db.session.commit()
        return redirect(url_for('collection'))

    # Pre-fill form with current movie data
    form.rating.data = str(movie.rating)
    form.review.data = movie.review
    return render_template("edit.html", movie=movie, form=form)

@app.route("/delete/<int:movie_id>")
def delete(movie_id):
    movie = db.session.get(Movie, movie_id)
    if movie:
        db.session.delete(movie)
        db.session.commit()
    return redirect(url_for('collection'))

def movie(title):
    url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": TMDB_api_key,
        "query": title,}
    response = requests.get(url, params=params)
    data = response.json()
    if data["results"]:
        return data["results"][0]
    else:
        return None

@app.route("/find", methods=["GET"])
def find():
    title = request.args.get("title")
    if not title:
        return redirect(url_for('add'))

    response = requests.get(
        "https://api.themoviedb.org/3/search/movie",
        params={"api_key": TMDB_api_key, "query": title}
    )
    data = response.json()
    return render_template("select.html", movies=data["results"])


@app.route("/select")
def select():
    tmdb_id = request.args.get("id")
    if not tmdb_id:
        return redirect(url_for('add'))

    movie_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
    params = {"api_key": TMDB_api_key}
    response = requests.get(movie_url, params=params)
    movie_data = response.json()

    new_movie = Movie(
        title=movie_data["title"],
        year=movie_data["release_date"].split("-")[0],
        rating=movie_data.get("vote_average", 0),
        description=movie_data.get("overview", ""),
        review="",  # Empty initially, you'll fill in edit
        ranking=db.session.query(Movie).count() + 1,
        img_url=f"https://image.tmdb.org/t/p/w500{movie_data.get('poster_path')}"
    )
    db.session.add(new_movie)
    db.session.commit()

    # Redirect to edit page for the new movie
    return redirect(url_for('edit', movie_id=new_movie.id))





if __name__ == '__main__':
    app.run(debug=True)
