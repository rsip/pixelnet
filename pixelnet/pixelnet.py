import tensorflow as tf

from keras import layers
from keras import models
from keras import regularizers
import keras.backend as K

def dense_bn(x, channels, name=None):
    x = layers.Dense(channels, name='{}_fc'.format(name), kernel_regularizer=regularizers.l2(1e-4))(x)
    x = layers.BatchNormalization(scale=False, name='{}_bn'.format(name))(x)
    return layers.Activation('relu', name=name)(x)

def flatten_pixels(nchannels):
    """ rearrange hypercolumns into a pixelwise data matrix """

    flatten = layers.Lambda(
        lambda t: K.reshape(t, (-1, nchannels)),
        output_shape=lambda s: (-1, s[-1]),
        name='flatten_pixel_features'
    )
    return flatten
    
def unflatten_pixels(inputs, nclasses=4, mode='dense'):
    
    if mode not in ('sparse', 'dense'):
        raise NotImplementedError
    
    if mode == 'dense':
        inputdata, = inputs
    elif mode == 'sparse':
        inputdata, inputcoord = inputs
        
    batchsize, h, w = tf.shape(inputdata)[0], tf.shape(inputdata)[1], tf.shape(inputdata)[2]
    
    if mode == 'dense':
        # note: output_shape wants the static shape (None, None, None, nclasses)
        # but reshape needs the dynamic shape (int, int, int, nclasses)

        b_dyn, h_dyn, w_dyn, _ = inputdata.shape
        unflatten = layers.Lambda(
            lambda t: K.reshape(t, (batchsize, h, w, nclasses)),
            output_shape=lambda s: (b_dyn, h_dyn, w_dyn, nclasses),
            name='unflatten_pixel_features'
        )
    elif mode == 'sparse':
        # note: output_shape wants the static shape (None, None, nclasses)
        # but reshape needs the dynamic shape (int, int, nclasses)
        # actually, batchsize can be either, but npix needs to be the dynamic value.
        npix = K.shape(inputcoord)[1]
        _, npix_dyn, _ = inputcoord.shape
        unflatten = layers.Lambda(
            lambda t: K.reshape(t, (batchsize, npix, nclasses)),
            # output_shape=lambda s: (4, 2048, nclasses),
            output_shape=lambda s: (batchsize, npix_dyn, nclasses),
            name='unflatten_pixel_features'
        )
        
    return unflatten
    
def build_model(hc_model, width=1024, depth=2, dropout_rate=0.5, nclasses=4, mode='dense', activation='softmax'):
    """ PixelNet: define an MLP model over a hypercolumn model given as input 

    @article{pixelnet,
      title={Pixel{N}et: {R}epresentation of the pixels, by the pixels, and for the pixels},
      author={Bansal, Aayush
              and Chen, Xinlei,
              and  Russell, Bryan
              and Gupta, Abhinav
              and Ramanan, Deva},
      Journal={arXiv preprint arXiv:1702.06506},
      year={2017}
    }

    From the paper and their notes on github, it seems like the semantic segmentation
    task should work either with linear classifier + BatchNorm, or with MLP without BatchNorm.

    activation: activation function for prediction layer. 'softmax' for classification, 'linear' for regression. """

    x = hc_model.output
    nchannels = tf.shape(x)[-1]
    x = flatten_pixels(nchannels)(x)
                       
    for idx in range(1, depth+1):
        x = dense_bn(x, width, name='mlp{}'.format(idx))
        x = layers.Dropout(dropout_rate)(x)

    x = layers.Dense(nclasses, activation=activation, name='predictions')(x)
    
    x = unflatten_pixels(hc_model.inputs, nclasses=nclasses, mode=mode)(x)

    return models.Model(inputs=hc_model.inputs, outputs=x)
