from flask import render_template
from flaskexample import app
import pandas as pd
from flask import request
import process_reviews as jc
import re
import numpy as np
from textblob import TextBlob
from nltk import tokenize
import nltk
from nltk.tokenize import RegexpTokenizer
from nltk.tokenize import WhitespaceTokenizer
from nltk.corpus import stopwords # Import the stop word list
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from nltk.stem.porter import PorterStemmer
import initial_model as initial_model
import cPickle as pickle
import os


###########    LOAD MODELS AND MATRIXES HERE.
reviews_vectorizer = pickle.load(open("data/review_classifier.pkl","rb"))
tfidf_reviews = pickle.load(open("data/review_tfidf.dat","rb"))

description_vectorizer = pickle.load(open("data/description_classifier.pkl","rb"))
tfidf_description = pickle.load(open("data/description_tfidf.dat","rb"))

hold_data = pickle.load(open("data/proc_info.pkl","rb"))
query_results = pickle.load(open("data/course_info.pkl","rb"))
#reviews = pickle.load(open("data/reviews.pkl","rb"))
#Collect and process reviews. Now in pickle form.
#collect_docs, collect_decs, collect_url_order,collect_course_sentiment=initial_model.initial_processing(query_results, reviews)
collect_docs=hold_data.proc_reviews
collect_decs=hold_data.proc_desc
collect_url_order=hold_data.course_url
collect_course_sentiment=hold_data.sentiment

@app.route('/')
@app.route('/index')
def index():
  return render_template("input.html")


@app.route('/slides')
def slide():
  return render_template("slides.html")


@app.route('/contact')
def contact():
  return render_template("contact.html")



@app.route('/about')
def about():
  return render_template("about.html")


@app.route('/backup_slides')
def backup_slides():
  return render_template("backup_slides.html")



@app.route('/input')
def xray_input():
  return render_template("input.html")


@app.route('/output')
def xray_output():


  #some reindexing by url
  documents=query_results.url
  df2=query_results.set_index('url')


  #Take user input, format and stem for analysis
  p_stemmer = PorterStemmer()
  keywords = request.args.get('user_keyword')
  input_string= keywords.replace(',',' ')

  input_words=[input_string]
  stemmed_input = [p_stemmer.stem(i) for i in jc.token_ws(input_string)]
  input_array= [i for i in jc.token_ws(input_string)]

  good_input=input_array
  
  #input check...keep track of bad words and remove
  stemmed_input, bad_output,good_input, error_list=initial_model.check_input(stemmed_input,\
          reviews_vectorizer,description_vectorizer, good_input )

  input_words=[' '.join(stemmed_input)]
  print input_words
  #print input_string
  save_string= ' '.join(good_input)
  print save_string

  #check to see if none of the keywords hit, send to error page
  if input_words[0]=='':
        return render_template("oops.html", the_result = bad_output)
  else:

  #Store the search results for use in the Xray
    with open('data/store_keys.dat', 'wb') as outfile:
      pickle.dump(input_words, outfile, pickle.HIGHEST_PROTOCOL)

    with open('data/store_unstem.dat', 'wb') as outfile:
      pickle.dump(save_string, outfile, pickle.HIGHEST_PROTOCOL)  

  #calculate similarities using input and review&description matrices
    review_cosine_scores=initial_model.get_cosine_similarities(input_words, reviews_vectorizer, tfidf_reviews)
    description_cosine_scores=initial_model.get_cosine_similarities(input_words, description_vectorizer, tfidf_description)


  #create a dataframe with results and add other information
    matching_matrix= pd.DataFrame({'course_url':collect_url_order,'review_score':review_cosine_scores, 
                              'description_score':description_cosine_scores,'sentiment':collect_course_sentiment})

    matching_matrix['total_score'] = matching_matrix.apply(lambda row:row.review_score+row.description_score,axis=1)
    matching_matrix_sort=matching_matrix.sort_values(by='total_score',ascending=False).reset_index(inplace=False,drop=True)


    matching_matrix_sort['title'] = matching_matrix_sort.course_url.apply(lambda x:df2.loc[x,'format_title'])
    matching_matrix_sort['company'] = matching_matrix_sort.course_url.apply(lambda x:df2.loc[x,'company'])
    matching_matrix_sort['num_rev'] = matching_matrix_sort.course_url.apply(lambda x:df2.loc[x,'num_rev'])
    matching_matrix_sort['description'] = matching_matrix_sort.course_url.apply(lambda x:df2.loc[x,'format_desc'])
    matching_matrix_sort['short_description'] = matching_matrix_sort.course_url.apply(lambda x:df2.loc[x,'short_desc'])

  #save the best url for the viz
    besturl=matching_matrix_sort.loc[0,'course_url']


   
  #find the scores for the different keywords in both reviews and descriptions
    keep_r_word, keep_r_value=initial_model.get_word_power(besturl,collect_url_order,tfidf_reviews,reviews_vectorizer, stemmed_input)
    keep_d_word, keep_d_value=initial_model.get_word_power(besturl,collect_url_order,tfidf_description,description_vectorizer, stemmed_input)
  
    power_r=pd.DataFrame({'stemmed_word':keep_r_word, 'whole_word':good_input, 'review_val':keep_r_value, 'description_val':keep_d_value})

  #power_r=pd.DataFrame({'word':keep_r_word, 'review_val':keep_r_value, 'description_val':keep_d_value})
  
    power_r['total'] = power_r.apply(lambda row:row.review_val+row.description_val,axis=1)
    power_results = power_r.sort_values(by='total',ascending=False).reset_index(inplace=False,drop=True)


  

  #Pull out top 5
    courses = []
    for i in range(1,5):
        courses.append(dict(url=matching_matrix_sort.iloc[i]['course_url'], 
          coursename=matching_matrix_sort.iloc[i]['title'], description=matching_matrix_sort.iloc[i]['short_description'],
          company=matching_matrix_sort.iloc[i]['company'], number= matching_matrix_sort.iloc[i]['num_rev'] ))
    the_result = ''


  #Pull out number 1 separately

    c1 = []
  
    c1.append(dict(url=matching_matrix_sort.loc[0,'course_url'], 
          coursename=matching_matrix_sort.loc[0,'title'], description=matching_matrix_sort.loc[0,'short_description'],
          company=matching_matrix_sort.loc[0,'company'], number= matching_matrix_sort.loc[0,'num_rev'] ))

   #save in a convenient format for D3
    power = []
    for i in range(0,5):
      if i < len(power_results.whole_word):
        power.append(dict( 
          word=power_results.iloc[i]['whole_word'], 
          rev_pow=power_results.iloc[i]['review_val'], 
          des_pow=power_results.iloc[i]['description_val'] ))
      else:
          power.append(dict( 
          word='', 
          rev_pow=0, 
          des_pow=0))
  
  #d=list(collect_course_sentiment)
 

  # for the Xray take reviews from best course
    cat_rev=[]
    take_rev=hold_data[hold_data.course_url==besturl].reviews
    for item in take_rev:
          cat_rev.append(item)

    keyword=power_results.whole_word[0]
    print keyword
  
  # calculate sentiment for keyword sentences
    keep_polarity=[]
    sentences=tokenize.sent_tokenize(str(cat_rev).decode('utf-8'))
    for sentence in sentences:
        if keyword in sentence:
            blob=TextBlob(sentence)
            keep_polarity.append(blob.sentiment.polarity)      


  #helps with binning rounding
    k=[x-0.01 for x in keep_polarity]

    d=list(k)


  #the_result = keywords.split(', ')
    the_result = input_array

  #pretty text output
    if len(the_result)==1:
      wordstring=( ' '.join( the_result))
    elif len(the_result)==2:
      wordstring=( ' and '.join( the_result)) 
    else:
      the_result[len(the_result)-1]='and '+str(the_result[len(the_result)-1])
      wordstring=( ", ".join( the_result)) 

# check if there were  bad words, send to different output pages if so..
    if bad_output=='':
      print 'all ok'
      return render_template("output.html", courses = courses, the_result = wordstring,power=power,c1=c1,dhist=d,keyword=keyword)
    else:
      print 'some bad output'
      return render_template("error_output.html", courses = courses, the_result = wordstring,power=power,c1=c1,dhist=d,keyword=keyword,bad_output=bad_output)

#####################################

@app.route('/output_xray')
def xray_output2():
  #load the original keywords
  old_data = pickle.load(open("data/store_keys.dat","rb"))
  old_data_pretty = pickle.load(open("data/store_unstem.dat","rb"))
  print old_data
  print old_data_pretty
 

  #reindex by url
  documents=query_results.url
  df2=query_results.set_index('url')


  #format input
  p_stemmer = PorterStemmer()
 
  input_string= ' '.join(old_data)#.replace(',',' ')

  input_string_pretty= old_data_pretty
  stemmed_input = [p_stemmer.stem(i) for i in jc.token_ws(input_string)]

  #special case error, for some reason it's changing how it stems database
  for ii,word in enumerate(stemmed_input):
    if word =='databa':
        stemmed_input[ii]='databas'
  

  input_words=[' '.join(stemmed_input)]
  input_array= jc.token_ws(input_string_pretty)


  #calculate similarities
  review_cosine_scores=initial_model.get_cosine_similarities(input_words, reviews_vectorizer, tfidf_reviews)
  description_cosine_scores=initial_model.get_cosine_similarities(input_words, description_vectorizer, tfidf_description)


  #store and rank by score
  matching_matrix= pd.DataFrame({'course_url':collect_url_order,'review_score':review_cosine_scores, 
                              'description_score':description_cosine_scores,'sentiment':collect_course_sentiment})

  matching_matrix['total_score'] = matching_matrix.apply(lambda row:row.review_score+row.description_score,axis=1)
  matching_matrix_sort=matching_matrix.sort_values(by='total_score',ascending=False).reset_index(inplace=False,drop=True)


  matching_matrix_sort['title'] = matching_matrix_sort.course_url.apply(lambda x:df2.loc[x,'format_title'])
  matching_matrix_sort['company'] = matching_matrix_sort.course_url.apply(lambda x:df2.loc[x,'company'])
  matching_matrix_sort['num_rev'] = matching_matrix_sort.course_url.apply(lambda x:df2.loc[x,'num_rev'])
  matching_matrix_sort['description'] = matching_matrix_sort.course_url.apply(lambda x:df2.loc[x,'format_desc'])
  matching_matrix_sort['short_description'] = matching_matrix_sort.course_url.apply(lambda x:df2.loc[x,'short_desc'])

  #find url of best matching class
  besturl=matching_matrix_sort.loc[0,'course_url']


  #get scores for specific keywords
  keep_r_word, keep_r_value=initial_model.get_word_power(besturl,collect_url_order,tfidf_reviews,reviews_vectorizer, stemmed_input)
  keep_d_word, keep_d_value=initial_model.get_word_power(besturl,collect_url_order,tfidf_description,description_vectorizer, stemmed_input)
  
  print keep_r_word, input_array
  power_r=pd.DataFrame({'stemmed_word':keep_r_word, 'whole_word':input_array, 'review_val':keep_r_value, 'description_val':keep_d_value})

#  power_r=pd.DataFrame({'word':keep_r_word, 'review_val':keep_r_value, 'description_val':keep_d_value})
  power_r['total'] = power_r.apply(lambda row:row.review_val+row.description_val,axis=1)
  power_results = power_r.sort_values(by='total',ascending=False).reset_index(inplace=False,drop=True)


  

  #grab top hits
  courses = []
  for i in range(1,5):
      courses.append(dict(url=matching_matrix_sort.iloc[i]['course_url'], 
        coursename=matching_matrix_sort.iloc[i]['title'], description=matching_matrix_sort.iloc[i]['short_description'],
        company=matching_matrix_sort.iloc[i]['company'], number= matching_matrix_sort.iloc[i]['num_rev'],
        sentiment=matching_matrix_sort.iloc[i]['sentiment'] ))
      the_result = ''



  c1 = []
  
  c1.append(dict(url=matching_matrix_sort.loc[0,'course_url'], 
        coursename=matching_matrix_sort.loc[0,'title'], description=matching_matrix_sort.loc[0,'short_description'],
        company=matching_matrix_sort.loc[0,'company'], number= matching_matrix_sort.loc[0,'num_rev'],
        sentiment=matching_matrix_sort.iloc[i]['sentiment'] ))

  #put scores in format for d3
  power = []
  for i in range(0,5):
    if i < len(power_results.whole_word):
      power.append(dict( 
        word=power_results.iloc[i]['whole_word'], 
        rev_pow=power_results.iloc[i]['review_val'], 
        des_pow=power_results.iloc[i]['description_val'] ))
    else:
        power.append(dict( 
        word='', 
        rev_pow=0, 
        des_pow=0))
  
  #get new keyword for xray
  keywords2 = request.args.get('user_keyword2')
  print keywords2
  

 

  #collect reviews, calculate sentiment for new keyword
  cat_rev=[]
  take_rev=hold_data[hold_data.course_url==besturl].reviews
  for item in take_rev:
        cat_rev.append(item)

  keyword=keywords2
  print keyword
  keep_polarity=[]
  sentences=tokenize.sent_tokenize(str(cat_rev).decode('utf-8'))
  for sentence in sentences:
      if keyword in sentence:
          blob=TextBlob(sentence)
          keep_polarity.append(blob.sentiment.polarity)      



  d=list(keep_polarity)

  #for binning
  k=[x-0.01 for x in keep_polarity]


  #the_result = keywords2.split(', ')
  the_result = input_array


  if len(the_result)==1:
    wordstring=( ' '.join( the_result))
  elif len(the_result)==2:
    wordstring=( ' and '.join( the_result)) 
  else:
    the_result[len(the_result)-1]='and '+str(the_result[len(the_result)-1])
    wordstring=( ", ".join( the_result)) 
  return render_template("output.html", courses = courses, the_result = wordstring,power=power,c1=c1,dhist=k,keyword=keywords2)







