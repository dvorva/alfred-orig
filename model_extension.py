import numpy as np
import pickle
import sklearn
import string
from sklearn.externals import joblib
from sklearn.svm import LinearSVC
from string import punctuation

def extract_feature_vector(command, word_list):
    """
    Convert text command into feature vector
    """
    feature_list = []
    feature_vector = np.zeros((len(word_list),), dtype=np.int)
    for key in word_list:
        if key in command:
            feature_vector[word_list[key]] = 1
    feature_list.append(feature_vector)
    feature_matrix = np.vstack(feature_list)
    return feature_matrix

def sanitize_input(text_in):
    """
    Convert text to lowercase, strip punctuation (excluding ?)
    """
    text_out = text_in.lower()
    for p in string.punctuation:
        if p != '?':
            text_out = text_out.replace(p, " " + p + " ")
    return text_out

def classify(text_in):
    """
    Classify input text, response to be described
    """
    clf = joblib.load('model.pkl')
    word_list = joblib.load('dictionary.pkl')
    feature_vector = extract_feature_vector(text_in, word_list)
    # Arbitrary boundary for attempting to classify text
    print np.amax(clf.decision_function(feature_vector))
    if np.amax(clf.decision_function(feature_vector)) < 0:
        return 0
    return clf.predict(feature_vector)[0]
