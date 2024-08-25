# -*- coding: utf-8 -*-
"""translate_and_summarize.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/14pqQEw6P9OL0CQjcXT9RKiKKgeBjAWfg
"""

import streamlit as st
from transformers import SeamlessM4TModel, AutoProcessor
from transformers import MarianMTModel, MarianTokenizer  # Import MarianTokenizer
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from transformers import T5ForConditionalGeneration, T5Tokenizer
import torch
import langid
import requests
from transformers import pipeline
from rouge import Rouge
from nltk.translate.bleu_score import sentence_bleu
from bert_score import score as bert_score
import nltk

nltk.download('punkt')

# Hugging Face API URL and headers
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
headers = {"Authorization": "Bearer YOUR_API_KEY_HERE"}  # Replace with your actual API key

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

def summarize_text(text, min_length, max_length):
    payload = {
        "inputs": text,
        "parameters": {
            "min_length": min_length,
            "max_length": max_length
        }
    }
    output = query(payload)

    # Check if the API response is valid
    if isinstance(output, list) and len(output) > 0:
        return output[0]['summary_text']
    else:
        return "Error: Unable to get a summary."

def summarize(text, min_length, max_length):
    max_input_length = 1024  # Maximum input length for BART model

    # Truncate input text if necessary
    if len(text.split()) > max_input_length:
        text = ' '.join(text.split()[:max_input_length])
        st.warning("Input text was too long and has been truncated.")

    summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

    try:
        summary = summarizer(text, max_length=max_length, min_length=min_length, do_sample=False)
        return summary[0]['summary_text']
    except Exception as e:
        st.error("An error occurred during summarization.")
        return None

def evaluate_summary(reference, summary):
    metrics = {}

    # ROUGE scores
    rouge = Rouge()
    rouge_scores = rouge.get_scores(summary, reference, avg=True)
    metrics['ROUGE-1'] = rouge_scores['rouge-1']['f']
    metrics['ROUGE-2'] = rouge_scores['rouge-2']['f']
    metrics['ROUGE-L'] = rouge_scores['rouge-l']['f']

    # BLEU score
    reference_tokens = [nltk.word_tokenize(reference)]
    summary_tokens = nltk.word_tokenize(summary)
    metrics['BLEU'] = sentence_bleu(reference_tokens, summary_tokens)

    # BERTScore
    P, R, F1 = bert_score([summary], [reference], lang="en")
    metrics['BERTScore (F1)'] = F1.mean().item()

    return metrics

def translate_text(input_text, output_language, model_index):
    # Detect the input language using langid
    input_language, _ = langid.classify(input_text)

    # List of available models
    model_choices = [
        "facebook/hf-seamless-m4t-medium",
        "Helsinki-NLP/opus-mt-en-roa",
        "google/madlad400-10b-mt"
    ]

    model_name = model_choices[model_index]

    if model_index == 0:
        model = SeamlessM4TModel.from_pretrained(model_name)
        processor = AutoProcessor.from_pretrained(model_name)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        inputs = processor(text=input_text, src_lang=input_language, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = model.generate(**inputs, tgt_lang=output_language, generate_speech=False)
        translated_text = processor.decode(outputs[0].tolist()[0], skip_special_tokens=True)

    elif model_index == 1:
        src_text = [">>" + output_language + "<<" + input_text]
        tokenizer = MarianTokenizer.from_pretrained(model_name)
        model = MarianMTModel.from_pretrained(model_name)
        translated = model.generate(**tokenizer(src_text, return_tensors="pt", padding=True))
        translated_text = tokenizer.decode(translated[0], skip_special_tokens=True)

    elif model_index == 2:
        model = T5ForConditionalGeneration.from_pretrained(model_name, device_map="auto")
        tokenizer = T5Tokenizer.from_pretrained(model_name)
        text = "<2" + output_language + ">" + input_text
        input_ids = tokenizer(text, return_tensors="pt").input_ids.to(model.device)
        outputs = model.generate(input_ids=input_ids)
        translated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

    return translated_text

# Streamlit app
st.title("MMD Summarizer with Translation")

text = st.text_area("Enter text to translate and summarize")

# Translation settings
output_language = st.text_input("Enter the language code you want to translate to (e.g., 'fra' for French):", value="fra")
model_index = st.selectbox("Select the translation model", options=[0, 1, 2], format_func=lambda x: [
    "SeamlessM4T", "Opus-MT", "MADLAD400"][x])

if st.button("Translate and Summarize"):
    if text:
        translated_text = translate_text(text, output_language, model_index)
        st.write("Translated Text:")
        st.write(translated_text)

        # Input fields for min and max length
        min_length = st.number_input("Minimum summary length (words):", min_value=5, max_value=100, value=25)
        max_length = st.number_input("Maximum summary length (words):", min_value=5, max_value=200, value=50)

        summary = summarize(translated_text, min_length=min_length, max_length=max_length)
        if summary:
            st.write("Summary:")
            st.write(summary)

            # Evaluation Metrics
            st.write("Evaluation:")
            st.write(f"Original Length: {len(text.split())} words")
            st.write(f"Summary Length: {len(summary.split())} words")
            st.write(f"Compression Ratio: {len(summary.split()) / len(text.split()):.2f}")

            # Calculate and display automatic metrics
            metrics = evaluate_summary(text, summary)
            st.write("ROUGE-1 Score:", metrics['ROUGE-1'])
            st.write("ROUGE-2 Score:", metrics['ROUGE-2'])
            st.write("ROUGE-L Score:", metrics['ROUGE-L'])
            st.write("BLEU Score:", metrics['BLEU'])
            st.write("BERTScore (F1):", metrics['BERTScore (F1)'])
    else:
        st.write("Please enter some text to translate and summarize.")