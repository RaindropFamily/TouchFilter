import os

import numpy as np
import scipy.io as sio
import tensorflow as tf
import trimesh as tm
from pyquaternion.quaternion import Quaternion as Q

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from tf_hand_kinematics import kinematics



class HandModel:
    def __init__(self, batch_size):
        # Hand shape
        mesh_base_dir = '/home/tengyu/Documents/DeepSDF/MujocoSDF/datagen/mesh/'
        self.parts = ['palm',
                    'thumb0', 'thumb1', 'thumb2', 'thumb3',
                    'index0', 'index1', 'index2', 'index3',
                    'middle0', 'middle1', 'middle2', 'middle3',
                    'ring0', 'ring1', 'ring2', 'ring3',
                    'pinky0', 'pinky1', 'pinky2', 'pinky3']

        self.key_pts = {p: np.mean(np.load(os.path.join(os.path.dirname(__file__), 'data', p + '.faces.npy')), axis=1) for p in self.parts if '0' not in p}
        self.normals = {p: np.load(os.path.join(os.path.dirname(__file__), 'data', p + '.face_normals.npy')) for p in self.parts if '0' not in p}

        self.tf_key_pts = {n: tf.constant(p, dtype=tf.float32) for (n,p) in self.key_pts.items()}
        self.tf_normals = {n: tf.constant(p, dtype=tf.float32) for (n,p) in self.normals.items()}

        self.surface_pts = {p: tf.constant(tm.load_mesh(os.path.join(os.path.dirname(__file__), 'data', 'hand', p + '.STL')).vertices, dtype=tf.float32) for p in self.parts}
        self.n_surf_pts = sum(x.shape[0] for x in self.surface_pts.values())

        # Input placeholder
        self.gpos = tf.placeholder(tf.float32, [batch_size, 3])
        self.grot = tf.placeholder(tf.float32, [batch_size, 3, 2])
        self.jrot = tf.placeholder(tf.float32, [batch_size, 22, 2])

        # Build model
        self.tf_forward_kinematics(self.gpos, self.grot, self.jrot)

    def arrange(self, pos, rot):
        for n in self.key_pts:
            self.out_key_pts[n] = np.matmul(Q(rot[n]).rotation_matrix, self.key_pts[n].T).T + pos[n]
            self.out_normals[n] = np.matmul(Q(rot[n]).rotation_matrix, self.normals[n].T).T
            self.out_surface_key_pts[n] = np.matmul(Q(rot[n]).rotation_matrix, self.surface_pts[n].T).T + pos[n]

    def tf_forward_kinematics(self, gpos, grot, jrot):
        xpos, xquat = kinematics(gpos, grot, jrot)
        out_key_pts = {n:tf.transpose(tf.matmul(xquat[n], tf.transpose(tf.pad(tf.tile(tf.expand_dims(self.tf_key_pts[n], axis=0), [gpos.shape[0], 1, 1]), paddings=[[0,0],[0,0],[0,1]], constant_values=1), perm=[0,2,1])), perm=[0,2,1])[...,:3] + tf.expand_dims(xpos[n], axis=1) for n in self.tf_key_pts}
        out_normals = {n:tf.transpose(tf.matmul(xquat[n], tf.transpose(tf.pad(tf.tile(tf.expand_dims(self.tf_normals[n], axis=0), [gpos.shape[0], 1, 1]), paddings=[[0,0],[0,0],[0,1]], constant_values=1), perm=[0,2,1])), perm=[0,2,1])[...,:3] for n in self.tf_normals}
        out_surface_key_pts = {n:tf.transpose(tf.matmul(xquat[n], tf.transpose(tf.pad(tf.tile(tf.expand_dims(self.surface_pts[n], axis=0), [gpos.shape[0], 1, 1]), paddings=[[0,0],[0,0],[0,1]], constant_values=1), perm=[0,2,1])), perm=[0,2,1])[...,:3] + tf.expand_dims(xpos[n], axis=1) for n in self.surface_pts}
        return out_key_pts, out_normals, out_surface_key_pts

# # Create a new plot
# figure = pyplot.figure()
# axes = mplot3d.Axes3D(figure)
# axes.add_collection3d(mplot3d.art3d.Poly3DCollection(mesh.vectors))

# # Auto scale to the mesh size
# scale = mesh.points.flatten(-1)
# axes.auto_scale_xyz(scale, scale, scale)

# # Show the plot to the screen
# pyplot.show()

if __name__ == "__main__":

    glove_data = sio.loadmat('/home/tengyu/Documents/DeepSDF/MujocoSDF/data/grasp/cup%d/cup%d_grasping_60s_1.mat'%(1, 1))['glove_data']

    hm = HandModel(glove_data.shape[0])
    print(hm.n_surf_pts)
    exit()

    gpos = glove_data[:,4:7]
    grot = np.array([Q(glove_data[i,1 + 28 * 3 + 4 : 1 + 28 * 3 + 8]).rotation_matrix[:,:2] for i in range(len(glove_data))])
    jrot = glove_data[:,1 + 28 * 3 + 28 * 4 + 7 : 1 + 28 * 3 + 28 * 4 + 29]
    jrot = np.stack([np.sin(jrot), np.cos(jrot)], axis=-1)

    out_key_pts, out_normals = hm.tf_forward_kinematics(tf.constant(gpos, dtype=tf.float32), tf.constant(grot, dtype=tf.float32), tf.constant(jrot, dtype=tf.float32))

    sess = tf.Session()
    out_key_pts, out_normals = sess.run([out_key_pts, out_normals])

    print(sum([x.shape[1] for (n, x) in out_key_pts.items()]))

    plt.ion()
    ax = plt.subplot(111, projection='3d')
    for fr in range(len(glove_data)):
        ax.cla()
        xmin, xmax, ymin, ymax, zmin, zmax = None, None, None, None, None, None
        for p in out_key_pts:
            ax.scatter(out_key_pts[p][fr,:,0], out_key_pts[p][fr,:,1], out_key_pts[p][fr,:,2], s=1)
            _xmin, _xmax, _ymin, _ymax, _zmin, _zmax = min(out_key_pts[p][fr,:,0]), max(out_key_pts[p][fr,:,0]), min(out_key_pts[p][fr,:,1]), max(out_key_pts[p][fr,:,1]), min(out_key_pts[p][fr,:,2]), max(out_key_pts[p][fr,:,2])
            if xmin is None or _xmin < xmin:
                xmin = _xmin
            if xmax is None or _xmax > xmax:
                xmax = _xmax
            if ymin is None or _ymin < ymin:
                ymin = _ymin
            if ymax is None or _ymax > ymax:
                ymax = _ymax
            if zmin is None or _zmin < zmin:
                zmin = _zmin
            if zmax is None or _zmax > zmax:
                zmax = _zmax
        x = (xmin + xmax)/2
        y = (ymin + ymax)/2
        z = (zmin + zmax)/2
        ax.set_xlim([x-0.15, x+0.15])
        ax.set_ylim([y-0.15, y+0.15])
        ax.set_zlim([z-0.15, z+0.15])
        plt.pause(1e-5)