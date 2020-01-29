
        #################################################
        ### THIS FILE WAS AUTOGENERATED! DO NOT EDIT! ###
        #################################################
        # file to edit: dev_nb/TextbookQA_App.ipynb

# Loading model dependencies
import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AlbertForQuestionAnswering
import sqlite3, os, pandas as pd
from scipy import stats
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity, pairwise_distances
from scipy.sparse import save_npz, load_npz
import pickle

# Downloading the model
tok = AutoTokenizer.from_pretrained("albert-base-v2")
model = AlbertForQuestionAnswering.from_pretrained("models/base") # ensure pytroch_model.bin and config files are saved in directory


# connecting to the DB
con = sqlite3.connect('examples/intro_to_nutrition/health.db')
curs = con.cursor()
# doc retrieval function
def get_doc_by_id(doc_id):
    return curs.execute(f"select * from documents where id='{doc_id}'").fetchall()

# loading files
X = load_npz("examples/intro_to_nutrition/health.npz")
vectorizer = pickle.load(open("examples/intro_to_nutrition/health_vectorizer.pkl","rb"))

def get_scores(text, vectorizer=vectorizer, X=X):
    y = vectorizer.transform([text])
    comp = cosine_similarity(X, y, dense_output=False)
    rows, _ = comp.nonzero()
    d = {i:float(comp[i,].todense()) for i in rows}
    return sorted(d.items(), key=lambda x: x[1], reverse=True)

def get_contexts(query,k=5,p=.6):
    top_docs = get_scores(query)[:k]
    top_scores = [i[1] for i in top_docs]
    norm_scores = np.array(top_scores)/sum(top_scores)
    top_ids, total = [],0
    for i,(idx,_) in enumerate(top_docs):
        if total > p: break
        top_ids.append(idx)
        total += norm_scores[i]
    return [get_doc_by_id(i)[0][1] for i in top_ids]

def pad_collate_x(samples, pad_idx=0, pad_first=False):
    max_len = max([len(s[0]) for s in samples])
    res = torch.zeros(len(samples), max_len).long() + pad_idx
    for i,s in enumerate(samples):
        if pad_first: res[i, -len(s[0]):] = torch.LongTensor(s[0])
        else:         res[i, :len(s[0]) ] = torch.LongTensor(s[0])
    return res

def listify(o):
    if o is None: return []
    if isinstance(o, list): return o
    if isinstance(o, str): return [o]
    if isinstance(o, Iterable): return list(o)
    return [o]

def prep_text(text, question, tok):
    tok_text, tok_ques = tok.tokenize(text), tok.tokenize(question)
    truncate_len = 512 - len(tok_ques) - 3*3
    res = ["[CLS]"] + tok_text[:truncate_len] + ["[SEP]"] + tok_ques + ["[SEP]"]
    return torch.tensor(tok.convert_tokens_to_ids(res)).unsqueeze(0)

def get_pred(texts, question, model, tok):
    if texts == []: return "could not find a section which matched query","N/A"
    texts = listify(texts)
    # 1. tokenize/encode the input text
    input_ids = pad_collate_x([prep_text(t, question, tok) for t in texts])
    # 2. extract the logits vector for the next possible token
    logits = model(input_ids)
    # 3. apply argmax to the logits so we have the probabilities of each index
    (start_probs,starts),(end_probs,ends) = [torch.max(out, dim=1) for out in logits]
    # 4. sort the sums of the starts and ends to determine which answers are the most ideal
    sorted_sums = np.argsort([sp+ep for (sp,ep) in zip(start_probs,end_probs)])[::-1]
    def _proc1(idx,start,end):
        if start > end: return
        elif start == end: end += 1
        pred = tok.convert_ids_to_tokens(input_ids[idx][start:end])
        return tok.convert_tokens_to_string(pred)

    # find the best answer
    for i,s in enumerate(sorted_sums):
        ans = _proc1(i,starts[i],ends[i])
        if ans is not None and "<pad>" not in ans: return ans, texts[i]
    return "unanswerable",texts[i]

import panel as pn
css = """ """ # use for custom css
pn.extension(raw_css=[css])

# creating the text input widget
question = pn.widgets.TextInput(placeholder="input a nutrient related question here")

question

# creating the markdown text pane where generated text will go
answer = pn.pane.Markdown("")
section = pn.pane.Markdown("",width=600,background="yellow")
section_spacer = pn.pane.Markdown("**Most Relevant Section:**")

# create the button widget
button = pn.widgets.Button(name="Submit",button_type="warning")

# writing the call back function when the generate_button is clicked
def click_cb(event):
    button.name, button.button_type = "Finding Answer...", "success" # change button to represent processing
    contexts = get_contexts(question.value,5)
    pred, best_section = get_pred(contexts, question.value, model, tok)
    section.object = best_section
    answer.object = pred
    button.name, button.button_type = "Submit", "warning" # change button back

# linking the on_click acton with the click_cb function
button.on_click(click_cb)

# compiling our app with the objects we have created thus far
app = pn.Column(pn.Column(question,button,answer,section_spacer,section))

# Building the final app with a title, description, images etc.
title_style = {"font-family":"impact"}
style = {"font-family":""}
title = pn.pane.Markdown("# **tbQA**",style=title_style)
desc = pn.pane.Markdown("Welcome to **TextBookQA**, a question answering demo for extracting answers from \
textbooks. This demo is based on the textbook, [*An Introduction to Nutrition*](https://www.oercommons.org/courses/an-introduction-to-nutrition-v1-0/view) \
(source: openbooks). Input a respective question and receive the answer and the relevant section.",style=style)
img1 = pn.pane.PNG("examples/intro_to_nutrition/health.png",height=300,align="center")
footer = pn.pane.HTML("""<a href="https://github.com/devkosal/albert-qa">Github""", align="center")
# Panel spacer object to center our title
h_spacer = pn.layout.HSpacer()
final_app = pn.Row(h_spacer, pn.Column( pn.Row(h_spacer,title,h_spacer) , desc, img1 ,app, footer), h_spacer)

# this command is needed in order to serve this app in production mode. (make sure to uncomment ofcourse)
final_app.servable()