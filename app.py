from flask import Flask, request, render_template, redirect, url_for, jsonify,flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO,emit
from werkzeug.utils import secure_filename
import os
import binascii


app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:hassan7709@localhost/memoverse'
app.config['SECRET_KEY'] = 'your_secret_key'

app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads/')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # ==2mb
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
socketio = SocketIO(app)

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    account = db.relationship('Account', backref='user', uselist=False, cascade="all, delete-orphan")

    def get_id(self):
        return self.user_id

class Account(db.Model):
    __tablename__ = 'account'
    acc_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    img = db.Column(db.Text)
    username = db.Column(db.String(30), nullable=False, unique=True)
    bio = db.Column(db.Text)
    follower_count = db.Column(db.Integer, default=0)
    following_count = db.Column(db.Integer, default=0)
    posts = db.relationship('Post', backref='account', lazy=True, cascade="all, delete-orphan")
    followers = db.relationship('Follow', foreign_keys='Follow.follower_id', backref='follower', lazy=True, cascade="all, delete-orphan")
    followings = db.relationship('Follow', foreign_keys='Follow.followed_id', backref='followed', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='account', lazy=True, cascade="all, delete-orphan")
    
    # Define foreign keys for notifications given and received
    given_notifications = db.relationship('Notification', foreign_keys='Notification.giver_id', backref='account_given', lazy=True)
    received_notifications = db.relationship('Notification', foreign_keys='Notification.receiver_id', backref='account_received', lazy=True)




class Follow(db.Model):
    __tablename__ = 'follow'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('account.acc_id'), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('account.acc_id'), nullable=False)

class Category(db.Model):
    __tablename__ = 'category'
    cat_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    catname = db.Column(db.String(150), nullable=False, unique=True)
    post = db.relationship('Post', backref='post_category', lazy=True, cascade="all, delete-orphan")

class Post(db.Model):
    __tablename__ = 'post'
    post_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    acc_id = db.Column(db.Integer, db.ForeignKey('account.acc_id'), nullable=False)
    img = db.Column(db.Text, nullable=False)
    caption = db.Column(db.String(300))
    category = db.Column(db.String(150), db.ForeignKey('category.catname',ondelete="SET NULL"))
    created_at = db.Column(db.TIMESTAMP, default=db.func.current_timestamp())
    likes_count = db.Column(db.Integer, default=0)
    likes = db.relationship('Liked', backref='post', lazy='dynamic')
    comments = db.relationship('Comment', backref='post', lazy=True, cascade="all, delete-orphan")
    saved_posts = db.relationship('Saved_Post', backref='post', lazy=True, cascade="all, delete-orphan")
    notification = db.relationship('Notification',backref='post')

class Saved_Post(db.Model):
    __tablename__ = 'saved_post'
    post_id = db.Column(db.Integer, db.ForeignKey('post.post_id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True)

class Liked(db.Model):
    __tablename__ = 'liked'
    like_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.post_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('account.acc_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class Comment(db.Model):
    __tablename__ = 'comment'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.post_id'), nullable=False)
    username = db.Column(db.Integer, db.ForeignKey('account.username'), nullable=False)
    cmnt = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP, default=db.func.current_timestamp())

class Notification(db.Model):
    __tablename__ = 'notification'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    giver_id = db.Column(db.Integer, db.ForeignKey('account.acc_id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('account.acc_id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.post_id'))
    txt = db.Column(db.Text)
    created_at = db.Column(db.TIMESTAMP, default=db.func.current_timestamp())

    # Define the foreign key relationship explicitly
    giver = db.relationship('Account', foreign_keys=[giver_id], backref='notifications_given', lazy=True)
    receiver = db.relationship('Account', foreign_keys=[receiver_id], backref='notifications_received', lazy=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

# Broadcast the notification to all connected clients
@socketio.on('notification')
def handle_notification(data):
    socketio.emit('notification', data)


def send_notification(notification):
    receiver = User.query.get(notification.receiver_id)
    if receiver:
        emit('notification', {
            'text': notification.txt,
            'post_id': notification.post_id,
            'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }, room=receiver.user_id, namespace='/notifications')



def capitalize_category_name(category_name):
    # Split the string into words
    words = category_name.split()

    # Capitalize the first letter of each word and make the rest lowercase
    capitalized_words = [word.capitalize() for word in words]

    # Join the words back into a string
    capitalized_category_name = ' '.join(capitalized_words)

    return capitalized_category_name




#handle error: not allowed file.....
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

#save image to a subfolder
def save_file(file, subfolder):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_id = binascii.hexlify(os.urandom(16)).decode('utf-8')
        new_filename = f"{unique_id}_{filename}"
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, new_filename)

        if not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], subfolder)):
            os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], subfolder), exist_ok=True)

        file.save(upload_path)
        return os.path.join(subfolder, new_filename)
    return None





# Login route
@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if not email or not password:
            return "Username or password missing", 400
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html')

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        new_user = User(email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('create_account'))
    return render_template('signup.html')

# Create account route
@app.route('/create_account', methods=['GET', 'POST'])
@login_required
def create_account():
    error = None  # Initialize error to None
    if request.method == 'POST':
        img = request.files.get('img')  # Use request.files.get() to safely retrieve the file
        if not img or img.filename == '':
            error = 'No selected file'  # Update error message
        else:
            upload_folder = 'profile_pictures'  # Define your upload folder
            os.makedirs(upload_folder, exist_ok=True)  # Ensure the folder exists
            
            uploaded_path = save_file(img, upload_folder)
            if uploaded_path:
                username = request.form['username']
                bio = request.form['bio']
                account = Account(user_id=current_user.user_id, img=uploaded_path, username=username, bio=bio)
                db.session.add(account)
                db.session.commit()
                return redirect(url_for('index'))
            else:
                error = 'File type not allowed or file size exceeded'  # Update error message

    return render_template('createprofile.html', error=error)

#edit profile
@app.route('/edit_account/<int:acc_id>', methods=['GET', 'POST'])
@login_required
def edit_account(acc_id):
    account = Account.query.get_or_404(acc_id)
    # Ensure the current user can only edit their own account
    if account.acc_id != current_user.account.acc_id:
        flash('You do not have permission to edit this account', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Handle image upload
        if 'img' in request.files:
            new_img = request.files['img']
            if new_img.filename != '':
                uploaded_path = save_file(new_img, 'profile_pictures')
                if uploaded_path:
                    account.img = uploaded_path
                else:
                    flash('File type not allowed or file size exceeded', 'danger')
                    return redirect(url_for('edit_account', acc_id=acc_id))
        
        # Update username
        new_username = request.form.get('username')
        if new_username:
            account.username = new_username

        # Update bio
        new_bio = request.form.get('bio')
        if new_bio:
            account.bio = new_bio


        db.session.commit()
        flash('Account updated successfully', 'success')


        return redirect(url_for('index'))
    return render_template('editprofile.html', account=account)



# Index view
@app.route('/index')
@login_required
def index():
    # Fetch all posts ordered by created_at descending
    posts = Post.query.order_by(Post.created_at.desc()).all()

    # Create a list to hold posts along with their latest comments
    posts_with_comments = []

    # Iterate over each post to fetch the latest 3 comments for each post
    for post in posts:
        latest_comments = Comment.query.filter_by(post_id=post.post_id).order_by(Comment.created_at.desc()).limit(3).all()
        posts_with_comments.append({
            'post': post,
            'latest_comments': latest_comments
        })

    # Render the template with the posts and their latest comments
    return render_template('index.html', posts_with_comments=posts_with_comments)


#follower
@app.route('/follower/<int:acc_id>')
def follower(acc_id):
    follower =Follow.query.filter_by(followed_id=acc_id).all()
    account=[]
    if follower:
        for follow in follower:
            accounts = Account.query.filter_by(acc_id=follow.follower_id).order_by(Account.username).all()
            account.extend(accounts)
            followinghim = Follow.query.filter_by(followed_id=follow.follower_id,follower_id=current_user.account.acc_id).all()
            hefollowing = Follow.query.filter_by(follower_id=follow.follower_id,followed_id=current_user.account.acc_id).all()
    else:
        return render_template('debug.html')
    return render_template('followers.html',follower=follower,account=account,followinghim = followinghim,hefollowing=hefollowing)

#following
@app.route('/following/<int:acc_id>')
def following(acc_id):
    followed =Follow.query.filter_by(follower_id=acc_id).all()
    account=[]
    if followed:
        for follow in followed:
            accounts = Account.query.filter_by(acc_id=follow.followed_id).order_by(Account.username).all()
            account.extend(accounts)
            followinghim = Follow.query.filter_by(followed_id=follow.followed_id,follower_id=current_user.account.acc_id).all()
            hefollowing = Follow.query.filter_by(follower_id=follow.follower_id,followed_id=current_user.account.acc_id).all()
    else:
        return render_template('debug.html')
    return render_template('following.html',followed=followed,account=account,followinghim = followinghim,hefollowing=hefollowing)


# Add post route
@app.route('/add_post', methods=['GET', 'POST'])
@login_required
def add_post():
    if request.method == 'POST':
        # Check if the image file is part of the request
        if 'img' not in request.files:
            return redirect(url_for('add_post', error='No file part'))

        img = request.files['img']
        if img.filename == '':
            return redirect(url_for('add_post', error='No selected file'))

        # Save the uploaded image
        uploaded_path = save_file(img, 'post_images')

        # Get the caption and category from the form
        caption = request.form['caption']
        category_name = request.form['category']

        category_name = capitalize_category_name(category_name)

        # Ensure the category exists
        category = Category.query.filter_by(catname=category_name).first()
        if not category:
            category = Category(catname=category_name)
            db.session.add(category)
            db.session.commit()

        # Create the new post
        post = Post(img=uploaded_path, caption=caption, acc_id=current_user.account.acc_id, category=category.catname)
        db.session.add(post)
        db.session.commit()

        # Notify the followers
        followers = current_user.account.followers
        for follower in followers:
            notification = Notification(
                receiver_id=follower.follower_id,  # Ensure this field matches your Notification model
                post_id=post.post_id,
                giver_id = current_user.account.acc_id,
                txt=f'New post from {current_user.account.username}'
            )
            db.session.add(notification)
            db.session.commit()
            send_notification(notification)

        return redirect(url_for('index'))
    return render_template('addpost.html')


#delete post
@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get(post_id)
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('index'))

#following
@app.route('/follow/<int:acc_id>',methods=['POST'])
@login_required
def follow(acc_id):
    account = Account.query.get(acc_id)
    current_account = Account.query.get(current_user.account.acc_id)
    follow = Follow.query.filter_by(follower_id = current_user.user_id,followed_id = acc_id).first()
    if follow :
        db.session.delete(follow)
        account.follower_count -=1
        current_account.following_count-=1
        db.session.commit()
        return redirect(url_for('othersprofile',acc_id=acc_id))
    else:
        new_follow = Follow(follower_id = current_user.user_id,followed_id = acc_id)
        db.session.add(new_follow)
        account.follower_count +=1
        current_account.following_count+=1
        db.session.commit()

         # Create a notification
        notification = Notification(
            receiver_id=acc_id,
            giver_id=current_user.account.acc_id,
            txt=f'started following you.'
        )
        db.session.add(notification)
        db.session.commit()
        send_notification(notification)

        return redirect(url_for('othersprofile',acc_id=acc_id))


@app.route('/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)

    # Check if the user has already liked the post
    like = Liked.query.filter_by(post_id=post_id, user_id=current_user.account.acc_id).first()
    if like:
        # User has already liked this post, so unlike it
        db.session.delete(like)
        post.likes_count-=1
        db.session.commit()
        return redirect(url_for('fullpost',post_id=post_id))
    else:
        # Add the like
        post.likes_count+=1
        like = Liked(post_id=post_id, user_id=current_user.account.acc_id)
        db.session.add(like)

        # Create a notification for the post owner
        notification = Notification(
            receiver_id=post.acc_id,
            giver_id = current_user.account.acc_id,
            post_id=post.post_id,
            txt=f'{current_user.account.username} liked your post'
        )
        db.session.add(notification)
        db.session.commit()

        return redirect(url_for('fullpost',post_id=post_id))



# Save post route
@app.route('/save_post/<int:post_id>', methods=['POST'])
@login_required
def save_post(post_id):
    user_id = current_user.user_id
    saved_post = Saved_Post.query.filter_by(post_id=post_id, user_id=user_id).first()
    if saved_post:
        db.session.delete(saved_post)
        db.session.commit()
        return redirect(url_for('fullpost',post_id=post_id))
    saved_post = Saved_Post(post_id=post_id, user_id=user_id)
    db.session.add(saved_post)
    db.session.commit()
    return redirect(url_for('fullpost',post_id=post_id))

# Add comment
@app.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    comment_text = request.form['comment']
    comment = Comment(cmnt=comment_text, post_id=post_id, username=current_user.account.username)
    db.session.add(comment)
    db.session.commit()

    post = Post.query.get(post_id)
    if post.acc_id != current_user.account.acc_id:
        notification = Notification(
            receiver_id=post.acc_id,
            giver_id=current_user.account.acc_id,
            post_id = post_id,
            txt=f'commented on your post.'
        )
        db.session.add(notification)
        db.session.commit()
        send_notification(notification)

    return redirect(url_for('fullpost', post_id=post_id))

# Delete comment
@app.route('/delete_comment/<int:id>', methods=['POST'])
@login_required
def delete_comment(id):
    comment = Comment.query.get(id)
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('fullpost',post_id=comment.post_id))


#categories explore
@app.route('/explore')
@login_required
def explore():
    categories = Category.query.all()
    post = Post.query.filter_by(category = Category.catname)
    return render_template('explore.html',categories = categories,post = post)


@app.route('/profile')
def profile():
    account = Account.query.filter_by(user_id = current_user.user_id).first()
    return render_template('profile.html',account=account)

@app.route('/othersprofile/<int:acc_id>')
def othersprofile(acc_id):
    account = Account.query.filter_by(acc_id = acc_id).first()
    follower = Follow.query.filter_by(followed_id=acc_id,follower_id=current_user.account.acc_id).first()
    following = Follow.query.filter_by(follower_id=acc_id,followed_id=current_user.account.acc_id).first()
    if acc_id==current_user.account.acc_id:
        return render_template('profile.html',account=account)
    return render_template('otherprofiles.html',account=account,follower=follower,following=following)

@app.route('/fullpost/<int:post_id>')
def fullpost(post_id):
    post = Post.query.filter_by(post_id=post_id).first()
    likes = Liked.query.filter_by(user_id = current_user.user_id,post_id=post_id).first()
    saved = Saved_Post.query.filter_by(user_id = current_user.user_id).first()
    comment = post.comments
    return render_template('fullpost.html', post=post, comments=comment,like=likes,save=saved,post_id=post_id)

@app.route('/saved')
def saved():
    savedposts = Saved_Post.query.filter_by(user_id=current_user.user_id)
    return render_template('savedposts.html',savedposts=savedposts)


@app.route('/notifications')
@login_required
def notifications():
    user_notifications = Notification.query.filter_by(receiver_id=current_user.user_id).order_by(Notification.created_at.desc()).all()
    for name in user_notifications:
        account = Account.query.filter_by(acc_id=name.giver_id).first()
    return render_template('notifications.html', notifications=user_notifications,account=account)

@app.route('/search_accounts')
@login_required
def search_accounts():
    query = request.args.get('query', '')
    results = []
    if query:
        results = Account.query.filter(Account.username.like(f'%{query}%')).all()
        for result in results:
            followinghim = Follow.query.filter_by(followed_id=result.acc_id,follower_id=current_user.account.acc_id).first()
            hefollowing = Follow.query.filter_by(follower_id=result.acc_id,followed_id=current_user.account.acc_id).first()
    else:
        return render_template('debug.html')
    return render_template('search.html', results=results,followinghim=followinghim,hefollowing=hefollowing)

if __name__ == "__main__":
    socketio.run(app,debug=True)
