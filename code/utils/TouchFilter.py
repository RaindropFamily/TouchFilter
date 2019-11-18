import numpy as np
import tensorflow as tf
from .pointnet_seg import get_model as pointnet_model

class TouchFilter:
    def __init__(self, n_pts, situation_invariant=False, penalty_strength=0):
        self.n_pts = n_pts
        self.situation_invariant = situation_invariant
        self.penalty_strength = tf.constant(penalty_strength, dtype=tf.float32)
        if self.situation_invariant:
            self.weight = tf.get_variable('des/touch/w', [1, self.n_pts, 2], initializer=tf.random_normal_initializer(stddev=0.001), trainable=True)
        else:
            # self.dense_1 = tf.layers.Dense(256, activation=tf.nn.relu)
            # self.dense_2 = tf.layers.Dense(256, activation=tf.nn.relu)
            pass
        pass
        
    def __call__(self, pts, normals, feat, cup_model, cup_r, penetration_penalty):
        # pts: B x N x 3
        if self.situation_invariant:
            weight = self.weight
        else:

            pts = tf.transpose(tf.matmul(
                    tf.transpose(cup_r, perm=[0,2,1]), 
                    tf.transpose(pts, perm=[0,2,1])), perm=[0, 2, 1])
            dists, grads = cup_model.predict(tf.reshape(pts, [-1,3]))
            dists = tf.reshape(dists, [pts.shape[0], -1, 1])  # B x N x 1
            grads = tf.reshape(grads, [pts.shape[0], -1, 3])

            normals /= tf.norm(normals, axis=-1, keepdims=True)
            grads /= tf.norm(grads, axis=-1, keepdims=True)
            angles = tf.reduce_sum(normals * grads, axis=-1, keepdims=True)

        pts = tf.concat([pts, dists, angles, feat], axis=-1)

        f0 = tf.nn.relu(-dists) + tf.nn.relu(dists) * penetration_penalty
        f1 = tf.nn.relu(dists) * penetration_penalty
        features = tf.concat([f0, f1], axis=-1)  # B x N x 2

        weight = pointnet_model(pts)[0]
        
        weight = tf.reshape(tf.nn.softmax(tf.reshape(weight, [-1, 2])), weight.shape)
        energies = weight * features # B x N x 2 

        return tf.reduce_mean(tf.reduce_sum(energies, axis=[1,2])), weight