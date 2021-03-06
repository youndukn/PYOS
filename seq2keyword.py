import tensorflow as tf
import numpy as np
import pickle

import models_trainable

from TokenizerWrap import TokenizerWrap

from tensorflow.python.keras.models import Model
from tensorflow.python.keras.layers import Input, Dense, GRU, Embedding
from tensorflow.python.keras.optimizers import RMSprop
from tensorflow.python.keras.callbacks import EarlyStopping, ModelCheckpoint, TensorBoard

from process_text import TextFilter

path_checkpoint = './check_p/21_checkpoint.keras'

queries = ["테러", "사고", "건강", "일본", "북미",
           "한미", "정상회담", "선거", "김기식", "외교", "국방", "국회",
           "청화대", "비핵화", "자유한국당", "더불어민주당", "개헌", "문재인", "대통령",
           "이명박", "암호화폐", "핵무기",
           "날씨", "중국", "미국", "북한",
           "FTA", "경제", "부동산",
           "미투", "박근혜"]

queries_unknown = ["쓰레기", "보이스피싱", "야구", "농구",
                   "스포츠", "개임", "자율주행", "사고",
                   "UAE", "졸음운전", "몰래카메라", "골프", "스마트폰", "전자발찌", "커피"
                                                                 "술", "마약", "폭력"]
political = ["일본", "북미", "한미", "정상회담", "선거", "김기식", "국방", "국회",
             "청화대", "비핵화", "자유한국당", "더불어민주당", "개헌", "문재인", "대통령",
             "이명박", "핵무기", "중국", "미국", "북한", "FTA", "경제", "부동산", "박근혜"]

non_political = []
mark_start = 'ssss '
mark_end = ' eeee'
mark_none = 'nnnn'


num_words = 150000


def sparse_cross_entropy(y_true, y_pred):
    """
    Calculate the cross-entropy loss between y_true and y_pred.

    y_true is a 2-rank tensor with the desired output.
    The shape is [batch_size, sequence_length] and it
    contains sequences of integer-tokens.

    y_pred is the decoder's output which is a 3-rank tensor
    with shape [batch_size, sequence_length, num_words]
    so that for each sequence in the batch there is a one-hot
    encoded array of length num_words.
    """

    # Calculate the loss. This outputs a
    # 2-rank tensor of shape [batch_size, sequence_length]
    loss = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y_true,
                                                          logits=y_pred)

    # Keras may reduce this across the first axis (the batch)
    # but the semantics are unclear, so to be sure we use
    # the loss across the entire 2-rank tensor, we reduce it
    # to a single scalar with the mean function.
    loss_mean = tf.reduce_mean(loss)

    return loss_mean

def translate(model_encoder,
              model_decoder,
              tokenizer_src,
              tokenizer_dest,
              input_text,
              model_embedding,
              true_output_text=None):
    """Translate a single text-string."""


    token_start = tokenizer_dest.word_index[mark_start.strip()]
    token_end = tokenizer_dest.word_index[mark_end.strip()]

    # Convert the input-text to integer-tokens.
    # Note the sequence of tokens has to be reversed.
    # Padding is probably not necessary.
    input_tokens = tokenizer_src.text_to_tokens(text=input_text,
                                                reverse=True,
                                                padding=True)

    # Get the output of the encoder's GRU which will be
    # used as the initial state in the decoder's GRU.
    # This could also have been the encoder's final state
    # but that is really only necessary if the encoder
    # and decoder use the LSTM instead of GRU because
    # the LSTM has two internal states.
    initial_state = model_encoder.predict(input_tokens)

    vector = initial_state

    # Max number of tokens / words in the output sequence.
    max_tokens = tokenizer_dest.max_tokens

    # Pre-allocate the 2-dim array used as input to the decoder.
    # This holds just a single sequence of integer-tokens,
    # but the decoder-model expects a batch of sequences.
    shape = (1, max_tokens)
    decoder_input_data = np.zeros(shape=shape, dtype=np.int)

    # The first input-token is the special start-token for 'ssss '.
    token_int = token_start

    # Initialize an empty output-text.
    output_text = ''

    # Initialize the number of tokens we have processed.
    count_tokens = 0


    # While we haven't sampled the special end-token for ' eeee'
    # and we haven't processed the max number of tokens.
    while token_int != token_end and count_tokens < max_tokens:
        # Update the input-sequence to the decoder
        # with the last token that was sampled.
        # In the first iteration this will set the
        # first element to the start-token.
        decoder_input_data[0, count_tokens] = token_int

        # Wrap the input-data in a dict for clarity and safety,
        # so we are sure we input the data in the right order.
        x_data = \
            {
                'decoder_initial_state': initial_state,
                'decoder_input': decoder_input_data
            }

        # Note that we input the entire sequence of tokens
        # to the decoder. This wastes a lot of computation
        # because we are only interested in the last input
        # and output. We could modify the code to return
        # the GRU-states when calling predict() and then
        # feeding these GRU-states as well the next time
        # we call predict(), but it would make the code
        # much more complicated.

        # Input this data to the decoder and get the predicted output.
        decoder_output = model_decoder.predict(x_data)
        decoder_embedding = model_embedding.predict(x_data)
        print(decoder_embedding)
        vector = decoder_embedding[0, count_tokens, :]
        # Get the last predicted token as a one-hot encoded array.
        token_onehot = decoder_output[0, count_tokens, :]
        indexes = token_onehot.argsort()[-3:][::-1]
        for index in indexes:
            print(index, token_onehot[index], tokenizer_dest.token_to_word(index))

        # Convert to an integer-token.
        token_int = np.argmax(token_onehot)

        # Lookup the word corresponding to this integer-token.
        sampled_word = tokenizer_dest.token_to_word(token_int)

        # Append the word to the output-text.
        output_text += " " + sampled_word

        # Increment the token-counter.
        count_tokens += 1
        break

    # Sequence of tokens output by the decoder.
    output_tokens = decoder_input_data[0]

    # Print the input-text.
    print("Input text:", input_text)

    # Print the translated output-text.
    print("Translated text:",  output_text)

    # Optionally print the true translated text.
    if true_output_text is not None:
        print("True output text:", true_output_text)

    print()
    return output_text.replace(mark_end, ""), vector


def get_vector(model_encoder,
              model_decoder,
              tokenizer_src,
              tokenizer_dest,
              input_text,
                model_embedding,
              true_output_text=None):
    """Translate a single text-string."""


    token_start = tokenizer_dest.word_index[mark_start.strip()]
    token_end = tokenizer_dest.word_index[mark_end.strip()]

    # Convert the input-text to integer-tokens.
    # Note the sequence of tokens has to be reversed.
    # Padding is probably not necessary.
    input_tokens = tokenizer_src.text_to_tokens(text=input_text,
                                                reverse=True,
                                                padding=True)

    # Get the output of the encoder's GRU which will be
    # used as the initial state in the decoder's GRU.
    # This could also have been the encoder's final state
    # but that is really only necessary if the encoder
    # and decoder use the LSTM instead of GRU because
    # the LSTM has two internal states.
    initial_state = model_encoder.predict(input_tokens)

    vector = initial_state

    return "", vector


def get_model(f_count):

    #
    encoder_input = Input(shape=(None, ), name='encoder_input')
    embedding_size = 128

    encoder_embedding = Embedding(input_dim=num_words,
                                  output_dim=embedding_size,
                                  name='encoder_embedding')

    state_size = 512

    encoder_gru1 = GRU(state_size, name='encoder_gru1',
                       return_sequences=True)
    encoder_gru2 = GRU(state_size, name='encoder_gru2',
                       return_sequences=True)
    encoder_gru3 = GRU(state_size, name='encoder_gru3',
                       return_sequences=False)


    def connect_encoder():
        # Start the neural network with its input-layer.
        net = encoder_input

        # Connect the embedding-layer.
        net = encoder_embedding(net)

        # Connect all the GRU-layers.
        net = encoder_gru1(net)
        net = encoder_gru2(net)
        net = encoder_gru3(net)

        # This is the output of the encoder.
        encoder_output = net

        return encoder_output

    encoder_output = connect_encoder()

    decoder_initial_state = Input(shape=(state_size,),
                                  name='decoder_initial_state')

    decoder_input = Input(shape=(None, ), name='decoder_input')

    decoder_embedding = Embedding(input_dim=f_count + 4,
                                  output_dim=embedding_size,
                                  name='decoder_embedding')

    decoder_gru1 = GRU(state_size, name='decoder_gru1',
                       return_sequences=True)
    decoder_gru2 = GRU(state_size, name='decoder_gru2',
                       return_sequences=True)
    decoder_gru3 = GRU(state_size, name='decoder_gru3',
                       return_sequences=True)

    decoder_dense = Dense(f_count + 4,
                          activation='linear',
                          name='decoder_output')

    def connect_decoder(initial_state):
        # Start the decoder-network with its input-layer.
        net = decoder_input

        # Connect the embedding-layer.
        net = decoder_embedding(net)

        # Connect all the GRU-layers.
        net = decoder_gru1(net, initial_state=initial_state)
        net = decoder_gru2(net, initial_state=initial_state)
        net = decoder_gru3(net, initial_state=initial_state)

        # Connect the final dense layer that converts to
        # one-hot encoded arrays.

        decoder_output = decoder_dense(net)

        return decoder_output, net

    decoder_output, net = connect_decoder(initial_state=encoder_output)

    model_train = Model(inputs=[encoder_input, decoder_input],
                        outputs=[decoder_output])

    model_encoder = Model(inputs=[encoder_input],
                          outputs=[encoder_output])

    decoder_output, decoder_embedding = connect_decoder(initial_state=decoder_initial_state)

    model_decoder = Model(inputs=[decoder_input, decoder_initial_state],
                          outputs=[decoder_output])

    model_embedding = Model(inputs=[decoder_input, decoder_initial_state],
                          outputs=[decoder_embedding])

    optimizer = RMSprop(lr=1e-3)

    decoder_target = tf.placeholder(dtype='int32', shape=(None, None))

    model_train.compile(optimizer=optimizer,
                        loss=sparse_cross_entropy,
                        target_tensors=[decoder_target])
    return model_train, model_encoder, model_decoder, model_embedding


def train_model(reload=False):

    models_trainable.initialized()

    data_array = []
    data_src = []
    data_dest = []
    if reload:

        text_filter = TextFilter()

        keyword_models = models_trainable.Keyword.select().where(
            models_trainable.Keyword.t_type >= 1,
            models_trainable.Keyword.t_type <= 4
        )
        keywords = []

        for keyword_model in keyword_models:
            keywords.append(keyword_model.name)

        videos = models_trainable.Video.select()

        for i, video in enumerate(videos):
            title = video.title
            text_filter.set_text(title)

            text_filter.regex_from_text(r'\[[^)]*\]')
            text_filter.remove_texts_from_text()
            text_filter.remove_pumsas_from_list()
            text_filter.remove_texts_from_text()

            matches = text_filter.get_matches(keywords)
            if len(matches)==0:
                data_array.append([mark_start + mark_none + mark_end,
                                   str(text_filter)])
            else:
                for keyword in matches:
                    data_array.append([mark_start + keyword + mark_end,
                                         str(text_filter)])

        f_count = len(keywords)
        print(len(data_array))
        for value in data_array:
            data_src.append(value[1])
            data_dest.append(value[0])

        # saving
        with open('count.pickle', 'wb') as handle:
            pickle.dump(len(keyword_models), handle, protocol=pickle.HIGHEST_PROTOCOL)

        # saving
        with open('data_src.pickle', 'wb') as handle:
            pickle.dump(data_src, handle, protocol=pickle.HIGHEST_PROTOCOL)

        # saving
        with open('data_dest.pickle', 'wb') as handle:
            pickle.dump(data_dest, handle, protocol=pickle.HIGHEST_PROTOCOL)
    else:

        # saving
        with open('count.pickle', 'rb') as handle:
            f_count = int(pickle.load(handle))

        # saving
        with open('data_src.pickle', 'rb') as handle:
            data_src = pickle.load(handle)

        # saving
        with open('data_dest.pickle', 'rb') as handle:
            data_dest = pickle.load(handle)


    tokenizer_src = TokenizerWrap(texts=data_src,
                                  padding='pre',
                                  reverse=True,
                                  num_words=num_words)

    tokenizer_dest = TokenizerWrap(texts=data_dest,
                                   padding='post',
                                   reverse=False,
                                   num_words=int(f_count) + 4)


    tokens_src = tokenizer_src.tokens_padded
    tokens_dest = tokenizer_dest.tokens_padded

    #
    encoder_input_data = tokens_src
    decoder_input_data = tokens_dest[:, :-1]
    decoder_output_data = tokens_dest[:, 1:]

    model_train, model_encoder, model_decoder, model_embedding = get_model(f_count)

    callback_checkpoint = ModelCheckpoint(filepath=path_checkpoint,
                                          monitor='val_loss',
                                          verbose=1,
                                          save_weights_only=True,
                                          save_best_only=True)

    callback_early_stopping = EarlyStopping(monitor='val_loss',
                                            patience=3, verbose=1)

    callback_tensorboard = TensorBoard(log_dir='./21_logs/',
                                       histogram_freq=0,
                                       write_graph=False)

    callbacks = [callback_early_stopping,
                 callback_checkpoint,
                 callback_tensorboard]

    try:
        model_train.load_weights(path_checkpoint)
    except Exception as error:
        print("Error trying to load checkpoint.")
        print(error)

    x_data = \
        {
            'encoder_input': encoder_input_data,
            'decoder_input': decoder_input_data
        }

    y_data = \
        {
            'decoder_output': decoder_output_data
        }

    validation_split = 500 / len(encoder_input_data)

    model_train.fit(x=x_data,
                    y=y_data,
                    batch_size=120,
                    epochs=10,
                    validation_split=validation_split,
                    callbacks=callbacks)


def get_vectors(input_videos):
    # saving
    with open('count.pickle', 'rb') as handle:
        f_count = int(pickle.load(handle))

    # saving
    with open('data_src.pickle', 'rb') as handle:
        data_src = pickle.load(handle)

    # saving
    with open('data_dest.pickle', 'rb') as handle:
        data_dest = pickle.load(handle)

    tokenizer_src = TokenizerWrap(texts=data_src,
                                  padding='pre',
                                  reverse=True,
                                  num_words=num_words)

    tokenizer_dest = TokenizerWrap(texts=data_dest,
                                   padding='post',
                                   reverse=False,
                                   num_words=f_count + 4)

    model_train, model_encoder, model_decoder, model_embedding =get_model(f_count)

    try:
        model_train.load_weights(path_checkpoint)
    except Exception as error:
        print("Error trying to load checkpoint.")
        print(error)

    keywords = []
    vectors = []
    for video in input_videos:
        keyword, vector = translate(model_encoder,
          model_decoder,
          tokenizer_src,
          tokenizer_dest,
          video.ptitle,
                                    model_embedding)
        keywords.append(keyword)
        vectors.append(vector)

    return keywords, vectors


def get_k_mean_clustered(input_videos, num_clusters = 40):

    vectors = []
    for video in input_videos:
        vectors.append(np.array(video.vector_processed[0]))

    np_vectors = np.array(vectors)

    def input_fn():
        return tf.train.limit_epochs(
            tf.convert_to_tensor(np_vectors, dtype=tf.float32), num_epochs=1)

    kmeans = tf.contrib.factorization.KMeansClustering(
        num_clusters=num_clusters, use_mini_batch=False)

    num_iterations = 2
    previous_centers = None

    for _ in range(num_iterations):
        kmeans.train(input_fn)
        cluster_centers = kmeans.cluster_centers()
        if previous_centers is not None:
            print ('delta:', cluster_centers - previous_centers)
        previous_centers = cluster_centers

    # map the input points to their clusters
    cluster_indices = list(kmeans.predict_cluster_index(input_fn))

    for video, cluster_index in zip(input_videos, cluster_indices):
        setattr(video, "cluster", cluster_index)

    for cc in range(num_clusters):
        for i, point in enumerate(np_vectors):
            if cc == cluster_indices[i]:
                video_title = input_videos[i].title
                cluster_index = cluster_indices[i]

    return cluster_centers

if __name__ == '__main__':
    train_model(False)