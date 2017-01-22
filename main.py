from flask import Flask, request, Response

import json
import requests
from random import random
import sys
from time import sleep

# import Google Cloud client libraries
from google.cloud import vision
from google.cloud.vision.feature import Feature
from google.cloud.vision.feature import FeatureTypes
from google.cloud import language
from google.cloud.exceptions import TooManyRequests

app = Flask(__name__)


def analyse_post(vision_client, features, language_client, raw_post):
    analysed_post = {'timestamp': raw_post['time'] * 1000,
                     'id': raw_post['id']}

    # download and analyse image
    img_url = raw_post['media']
    i = requests.get(img_url)
    image = vision_client.image(content=i.content)
    annotations = image.detect(features)

    faces = []
    emotions = ('joy', 'anger', 'sorrow', 'surprise')
    if len(getattr(annotations, 'faces')) > 0:
        for face in getattr(annotations, 'faces'):
            f = {}
            for emotion in emotions:
                f[emotion] = getattr(face.emotions, emotion).value
            faces.append(f)
    analysed_post['faces'] = faces

    # for attr in ('labels', 'logos', 'texts'):
    for attr in ('labels', 'logos'):
        analysed_post[attr] = []
        if len(getattr(annotations, attr)) > 0:
            for v in getattr(annotations, attr):
                analysed_post[attr].append(v.description)

    # analyse caption

    if 'text' in raw_post:
        document = language_client.document_from_text(
            raw_post['text'])

        # Detects the sentiment of the text
        sentiment = document.analyze_sentiment()
        analysed_post['caption_sentiment'] = {
            'score': sentiment.score,
            'magnitude': sentiment.magnitude}

    return analysed_post


@app.route('/analyse', methods=['POST'])
def analyse():
    raw_posts = request.get_json()

    print('Received {} posts to analyse'.format(len(raw_posts)))

    # instantiate Google Cloud clients
    # Instantiates a vision client
    vision_client = vision.Client()

    features = [Feature(FeatureTypes.LABEL_DETECTION, 10),
                Feature(FeatureTypes.FACE_DETECTION, 10),
                Feature(FeatureTypes.LOGO_DETECTION, 10),
                # Feature(FeatureTypes.TEXT_DETECTION, 10),
                Feature(FeatureTypes.LANDMARK_DETECTION, 10)]

    # Instantiates a language client
    language_client = language.Client()

    def generate_analyses():
        first_post_out = False
        count = 0

        for raw_post in raw_posts:
            success = False
            tries = 0
            maximum_backoff = 64

            while not success:
                try:
                    if raw_post['type'] == 'image':
                        analysed_post = analyse_post(vision_client, features,
                                                     language_client, raw_post)
                    success = True
                except TooManyRequests:
                    backoff = min(2 ** tries, maximum_backoff) + random()
                    print(
                        'Rate limited, backing off for {:.2f} seconds'.format(
                            backoff), file=sys.stderr)
                    sleep(backoff)
                    tries += 1

            count += 1
            print('Analysed {} posts.'.format(count))

            if raw_post['type'] != 'image':
                continue

                # if raw_post['type'] == 'image':
                #     yield analysed_post

            if not first_post_out:
                first_post_out = True
                yield '[' + json.dumps(analysed_post)
            else:
                yield ',' + json.dumps(analysed_post)

        yield ']'

    return Response(generate_analyses(), mimetype='application/json')

    # response = []
    # for analysis in generate_analyses():
    #     response.append(analysis)
    #
    # return Response(json.dumps(response), mimetype='application/json')


@app.route('/version')
def version():
    return '0.3.0'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
