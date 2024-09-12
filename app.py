from flask import Flask, render_template, request, redirect, url_for, flash
from pyngrok import ngrok
from dotenv import load_dotenv
import os
import json
import pandas as pd 
import re
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()
app = Flask(__name__)


app.secret_key = os.getenv('SECRET_KEY', 'fallback_secret_key')
articleCategory = ['', 'أحدث الأبحاث والدراسات', 'الأخبار والفعاليات']

# Article [aStatus=1 published  , aStatus=2 archived  , aStatus=3 unpublished  , aStatus=0 deleted]
# Article [atype = 1 reasearch & studies, atype=2 news & event] 

#region Utility function for loading and saving content
# Load Json

def handle_json(file_name, content=None, mode='load'):
    file_path = os.path.join('data', f'{file_name}.json')
    if mode == 'load':
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            return []
    elif mode == 'save' and content is not None:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(content, file, ensure_ascii=False, indent=4)

    
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        for item in data:
            if item['id'] == target_id:
                for key, value in new_data.items():
                    item[key] = value
                break
        else:
            # Record not found
            return False

        with open(json_file, 'w') as f:
            json.dump(data, f, indent=4)

        return True
    except Exception as e:
        print(f"Error updating record: {e}")
        return False
# Sorting Json Contain
def sort_by_published_date(articles):
    return sorted(articles, key=lambda article: (article['posted_date'], article['id']) , reverse=True)
    

def remove_items_by_value(filename, key, value):
    """Removes items from a JSON file based on a specific key and value.

    Args:
        filename (str): The name of the JSON file.
        key (str): The key to check for the value.
        value (any): The value to search for.

    Returns:
        None: The function modifies the JSON file in-place.
    """
    with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

    new_data = []
    for item in data:
        if item.get(key) != value:
            new_data.append(item)

    with open(filename, 'w') as f:
        json.dump(new_data, f, indent=4)

# UpLoad Multiple Image
def upload_multiple_images(images, upload_dir='static/images'):

  uploaded_filenames = []
  for image in images:
    if image and image.filename:
      # Get a unique filename to avoid overwriting
      filename, extension = os.path.splitext(image.filename)
      base_filename, _ = os.path.splitext(filename)
      counter = 1
      while os.path.exists(os.path.join(upload_dir, filename + extension)):
        filename = f"{base_filename}_{counter}"
        counter += 1

     
      # Save the image    
      image.save(os.path.join('static', 'images', filename + extension))
      uploaded_filenames.append(filename + extension)

  return uploaded_filenames


#endregion

#region Live WebSite Modules 

# 1. HomePage 
@app.route('/', methods=['GET'])
def index():            
    content = {
        'articlesType1':sort_by_published_date([article for article in handle_json('articles') if article['aType'] == 1 and article['aStatus'] == 1])   ,      
        'articlesType2':sort_by_published_date([article for article in handle_json('articles') if article['aType'] == 2 and article['aStatus'] == 1])   
    }    

    return render_template('index.html',current_page='index', content=content)

# 2. Archive Page
@app.route('/archive', methods=['GET'])
def archive():            
    content = {
        'archive_articlesType1': sort_by_published_date([article for article in handle_json('articles') if article['aType'] == 1 and article['aStatus'] == 2  ])   ,      
        'archive_articlesType2':sort_by_published_date ([article for article in handle_json('articles') if article['aType'] == 2 and article['aStatus'] == 2])   
    }    

    return render_template('archive.html',current_page='archive', content=content)

# 3. Article  (all article type) Page
# article should be published OR archived astatus = 1 / 2
@app.route('/article/<articleid>')
def news(articleid):
    content = handle_json('articles')
    # Article [aStatus=1 published  , aStatus=2 archived  , aStatus=3 unpublished  , aStatus=0 deleted]
    news_item = next((item for item in content if item['id'] ==int(articleid) and (item["aStatus"] == 1 or item["aStatus"] == 2)   ), None)
    
    if not news_item:
        return "<center><h1>Error: 404: Article not Found<h1><center>", 404

    return render_template(f'/content_template.html', 
                           posted_date =news_item['posted_date'] ,
                           title=news_item['title'], 
                           image_filename=news_item['image'], 
                           youtubes=news_item['youtubes'], 
                           content_text=news_item['full_text'])

# 4. Goals Page				
@app.route('/goals')
def goals():
    return render_template('goals.html',current_page='goals')

# 5. Contact Us Page
@app.route('/contact_us')
def contact_us():
    return render_template('contact_us.html',current_page='contact_us')

#endregion

#region Login Module
# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
# A simple user class
class User(UserMixin):
    def __init__(self, id):
        self.id = id

# Dummy user (for this example, you'll likely want to use a database in production)
users = {'mohamad': generate_password_hash('milan123')}  # Replace with your desired username and password
@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and check_password_hash(users[username], password):
            user = User(username)
            login_user(user)
            return redirect(url_for('manage'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

#endregion 

#region CMS Module

# 1. CMS DashPage
@app.route('/manage')
@login_required
def manage():
    content = {
        'article_deleted': sort_by_published_date([article for article in handle_json('articles') if article['aStatus'] == 0  ]) , 
        'article_published':  sort_by_published_date([article for article in handle_json('articles') if article['aStatus'] ==1]),
        'article_archived': sort_by_published_date([article for article in handle_json('articles') if article['aStatus'] == 2]) ,
        'article_unpublished': sort_by_published_date([article for article in handle_json('articles') if article['aStatus'] == 3]) 
    }    
    return render_template('manage.html', content=content,products=articleCategory)

# 2. DashPage Add New Article
@app.route('/add_content', methods=['POST'])
@login_required
def add_content():
    aType =int(request.form.get('item_type')) 
    aStatus= int(request.form.get('item_status')) 
    title =request.form.get('title').replace('"', "'")    
    description =request.form.get('description').replace('"', "'")
    content_text =request.form.get('content').replace('"', "'")
    youtubes =request.form.get('youtubes')   
    images1 = request.files.getlist('images')  
    uploaded_filenames = upload_multiple_images(images1)

    content = handle_json('articles')
    # Convert JSON to DataFrame for easier manipulation
    df = pd.DataFrame(content)

    # Extract ID column and find the maximum value
    max_id = df['id'].max()+ 1
  
    new_item = {
        "id":int(max_id),
        "aType":aType,
        "aStatus": aStatus,
        "title": title,
        "description": description,
        "full_text": content_text,        
        "image": uploaded_filenames,      
        "youtubes": youtubes,      
        "posted_date": request.form.get('articleDate', '')            
    }

    content.append(new_item)
    handle_json('articles', content, mode='save')
    flash('Content added successfully.', 'success')
    return redirect(url_for('manage'))

# 3. Save edit Article 
@app.route('/saveedit_content', methods=['POST'])
@login_required
def saveedit_content(): 

    article_id_str =request.form.get('articleID')
    aType =int(request.form.get('item_type')) 
    aStatus= int(request.form.get('item_status')) 
    title =request.form.get('title').replace('"', "'")    
    description =request.form.get('description').replace('"', "'")
    content_text =request.form.get('content').replace('"', "'")
    youtubes =request.form.get('youtubes')   
    images1 = request.files.getlist('images')  
    posted_date= request.form.get('articleDate')
    uploaded_filenames = upload_multiple_images(images1)  
    #oldimg =request.form.get('imgList').replace("'","").replace(" ","")    
    oldimg =request.form.get('hfSort').replace("'","").replace(" ","")    


    if not bool(oldimg):
        #return "empty string"  no previous image
        combinedList = uploaded_filenames    
    else:
        oldImg1 =oldimg.split(",")
        combinedList = uploaded_filenames + oldImg1
       

     # Check if articleID is None or empty
    if not article_id_str:
        return "Error: 'articleID' is missing or empty in the request.", 400
    # Convert articleID to integer
    try:
        a_id = int(article_id_str)

        data = handle_json('articles')
        for item in data:
            if item['id'] ==  a_id:               
                item['title'] = title
                item['description'] = description
                item['full_text'] = content_text
                item['aType'] = aType
                item['aStatus'] = aStatus
                item['youtubes'] = youtubes
                item['posted_date']  = posted_date       
                item['image'] = combinedList   
          
                handle_json('articles', data, mode='save')
                
                return redirect(url_for('manage'))            
    except ValueError:
        return "Error: 'articleID' must be an integer.", 400


# 4. Edit Article 
@app.route('/edit_content', methods=['GET'])
@login_required
def edit_content():
    item_id = int(request.args.get('item_ID'))
    content = handle_json('articles')   
    news_item = next((item for item in content if item['id'] == int(item_id)), None)
    if not news_item:
        return "<center><h1>Error: 404: Article not Found<h1><center>", 404
    else:
        return render_template(f'/edit_content.html',
                           articleid=news_item['id'],
                           posted_date=news_item['posted_date'],
                           aType=news_item['aType'],
                           aStatus=news_item['aStatus'],
                           title=news_item['title'],
                           description=news_item['description'],
                           image_filename=news_item['image'],
                           youtubes=news_item['youtubes'],                          
                           content_text=news_item['full_text'])

# 5. Delete Article 
@app.route('/delete_content', methods=['GET'])
@login_required
def delete_content():
    item_id = int(request.args.get('item_ID'))

    # Example usage
    filename = 'data/articles.json'
    key = 'id'
    value = item_id

    remove_items_by_value(filename, key, value)
    
    return redirect(url_for('manage'))


# 6. Delete Image 
@app.route('/delete_image', methods=['GET'])
@login_required
def delete_image():
    # Retrieve parameters from the request
    article_id_str = request.args.get('item_ID')
    item_image = request.args.get('item_image')

    # Debugging output
    print(f"Received article_id: {article_id_str}")
    print(f"Received item_image: {item_image}")

    if not article_id_str or not item_image:
        return "Error: 'item_ID' or 'item_image' is missing or empty in the request.", 400

    # Convert article_ID to integer
    try:
        a_id = int(article_id_str)
    except ValueError:
        return "Error: 'item_ID' must be an integer.", 400

    try:
        # Load JSON data from the file
        content = handle_json('articles')
        
        # Debugging output
        print(f"Loaded content: {content}")

        # Find the article by ID
        news_item = next((item for item in content if item['id'] == a_id), None)

        if not news_item:
            return "Error: Article with the specified ID not found.", 404

        # Remove the specified image from the list of images
        if 'image' in news_item:
            if item_image in news_item['image']:
                news_item['image'].remove(item_image)

                # Save the updated content back to the JSON file
                handle_json('articles', content, mode='save')
                return redirect(url_for('edit_content', item_ID=article_id_str))

                
                
            else:
                return "Error: Image not found in the article.", 404
        else:
            return "Error: 'image' field not found in the article.", 400

    except Exception as e:
        print(f"Exception occurred: {e}")  # Debugging output
        return f"Error: {e}", 500
 
#endregion
if __name__ == '__main__':
    # Authenticate and create ngrok tunnel
    ngrok_token = '2lviQVacZYjUmgOlaWUF0qKNLoj_3DYT8644H9HBQZKULqfUH'
    if ngrok_token:
        ngrok.set_auth_token(ngrok_token)

    # Open the ngrok tunnel
    public_url = ngrok.connect(5000)
    print(f" * ngrok tunnel: {public_url}")

    # Run the Flask app
    app.run()
