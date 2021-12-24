#import pose_utils
import os
import numpy as np
import tensorflow as tf
import skimage.transform as st
from skimage.transform import resize
from scipy.ndimage import gaussian_filter
import torch

# The relative path depends on which of the two scripts we use to run this functionality (inference.py or main.py)
pose_estimation_model_path = './checkpoints/pose_estimator.h5'
if not os.path.exists(os.path.abspath('./checkpoints/pose_estimator.h5')):
    pose_estimation_model_path = './human_body_generation/checkpoints/pose_estimator.h5'
model = tf.keras.models.load_model(pose_estimation_model_path)


mapIdx = [[31,32], [39,40], [33,34], [35,36], [41,42], [43,44], [19,20], [21,22],
          [23,24], [25,26], [27,28], [29,30], [47,48], [49,50], [53,54], [51,52],
          [55,56], [37,38], [45,46]]

limbSeq = [[2,3], [2,6], [3,4], [4,5], [6,7], [7,8], [2,9], [9,10],
           [10,11], [2,12], [12,13], [13,14], [2,1], [1,15], [15,17],
           [1,16], [16,18], [3,17], [6,18]]

# This function computes the coordinates of the pose estimation
def compute_cordinates(heatmap_avg, paf_avg, oriImg, th1=0.1, th2=0.05):
    all_peaks = []
    peak_counter = 0

    for part in range(18):
        map_ori = heatmap_avg[:,:,part]
        map = gaussian_filter(map_ori, sigma=3)

        map_left = np.zeros(map.shape)
        map_left[1:,:] = map[:-1,:]
        map_right = np.zeros(map.shape)
        map_right[:-1,:] = map[1:,:]
        map_up = np.zeros(map.shape)
        map_up[:,1:] = map[:,:-1]
        map_down = np.zeros(map.shape)
        map_down[:,:-1] = map[:,1:]

        peaks_binary = np.logical_and.reduce((map>=map_left, map>=map_right, map>=map_up, map>=map_down, map > th1))
        peaks = list(zip(np.nonzero(peaks_binary)[1], np.nonzero(peaks_binary)[0])) # note reverse

        peaks_with_score = [x + (map_ori[x[1],x[0]],) for x in peaks]
        id = range(peak_counter, peak_counter + len(peaks))
        peaks_with_score_and_id = [peaks_with_score[i] + (id[i],) for i in range(len(id))]

        all_peaks.append(peaks_with_score_and_id)
        peak_counter += len(peaks)

    connection_all = []
    special_k = []
    mid_num = 10

    for k in range(len(mapIdx)):
        score_mid = paf_avg[:,:,[x-19 for x in mapIdx[k]]]
        candA = all_peaks[limbSeq[k][0]-1]
        candB = all_peaks[limbSeq[k][1]-1]
        nA = len(candA)
        nB = len(candB)
        indexA, indexB = limbSeq[k]
        if(nA != 0 and nB != 0):
            connection_candidate = []
            for i in range(nA):
                for j in range(nB):
                    vec = np.subtract(candB[j][:2], candA[i][:2])
                    norm = np.sqrt(vec[0]*vec[0] + vec[1]*vec[1])
                    vec = np.divide(vec, norm)

                    startend = list(zip(np.linspace(candA[i][0], candB[j][0], num=mid_num),
                                   np.linspace(candA[i][1], candB[j][1], num=mid_num)))

                    vec_x = np.array([score_mid[int(round(startend[I][1])), int(round(startend[I][0])), 0]
                                      for I in range(len(startend))])
                    vec_y = np.array([score_mid[int(round(startend[I][1])), int(round(startend[I][0])), 1]
                                      for I in range(len(startend))])

                    score_midpts = np.multiply(vec_x, vec[0]) + np.multiply(vec_y, vec[1])
                    score_with_dist_prior = sum(score_midpts)/len(score_midpts) + min(0.5*oriImg.shape[0]/norm-1, 0)
                    criterion1 = len(np.nonzero(score_midpts > th2)[0]) > 0.8 * len(score_midpts)
                    criterion2 = score_with_dist_prior > 0
                    if criterion1 and criterion2:
                        connection_candidate.append([i, j, score_with_dist_prior, score_with_dist_prior+candA[i][2]+candB[j][2]])

            connection_candidate = sorted(connection_candidate, key=lambda x: x[2], reverse=True)
            connection = np.zeros((0,5))
            for c in range(len(connection_candidate)):
                i,j,s = connection_candidate[c][0:3]
                if(i not in connection[:,3] and j not in connection[:,4]):
                    connection = np.vstack([connection, [candA[i][3], candB[j][3], s, i, j]])
                    if(len(connection) >= min(nA, nB)):
                        break

            connection_all.append(connection)
        else:
            special_k.append(k)
            connection_all.append([])

    # last number in each row is the total parts number of that person
    # the second last number in each row is the score of the overall configuration
    subset = -1 * np.ones((0, 20))
    candidate = np.array([item for sublist in all_peaks for item in sublist])

    for k in range(len(mapIdx)):
        if k not in special_k:
            partAs = connection_all[k][:,0]
            partBs = connection_all[k][:,1]
            indexA, indexB = np.array(limbSeq[k]) - 1

            for i in range(len(connection_all[k])): #= 1:size(temp,1)
                found = 0
                subset_idx = [-1, -1]
                for j in range(len(subset)): #1:size(subset,1):
                    if subset[j][indexA] == partAs[i] or subset[j][indexB] == partBs[i]:
                        subset_idx[found] = j
                        found += 1

                if found == 1:
                    j = subset_idx[0]
                    if(subset[j][indexB] != partBs[i]):
                        subset[j][indexB] = partBs[i]
                        subset[j][-1] += 1
                        subset[j][-2] += candidate[partBs[i].astype(int), 2] + connection_all[k][i][2]
                elif found == 2: # if found 2 and disjoint, merge them
                    j1, j2 = subset_idx
                    print("found = 2")

                    membership = ((subset[j1]>=0).astype(int) + (subset[j2]>=0).astype(int))[:-2]
                    if len(np.nonzero(membership == 2)[0]) == 0: #merge
                        subset[j1][:-2] += (subset[j2][:-2] + 1)
                        subset[j1][-2:] += subset[j2][-2:]
                        subset[j1][-2] += connection_all[k][i][2]
                        subset = np.delete(subset, j2, 0)
                    else: # as like found == 1
                        subset[j1][indexB] = partBs[i]
                        subset[j1][-1] += 1
                        subset[j1][-2] += candidate[partBs[i].astype(int), 2] + connection_all[k][i][2]

                # if find no partA in the subset, create a new subset
                elif not found and k < 17:
                    row = -1 * np.ones(20)
                    row[indexA] = partAs[i]
                    row[indexB] = partBs[i]
                    row[-1] = 2
                    row[-2] = sum(candidate[connection_all[k][i,:2].astype(int), 2]) + connection_all[k][i][2]
                    subset = np.vstack([subset, row])

    # delete some rows of subset which has few parts occur
    deleteIdx = [];
    for i in range(len(subset)):
        if subset[i][-1] < 4 or subset[i][-2]/subset[i][-1] < 0.4:
            deleteIdx.append(i)
    subset = np.delete(subset, deleteIdx, axis=0)

    if len(subset) == 0:
        return np.array([[-1, -1]] * 18).astype(int)

    cordinates = []
    result_image_index = np.argmax(subset[:, -2])

    for part in subset[result_image_index, :18]:
        if part == -1:
            cordinates.append([-1, -1])
        else:
            Y = candidate[part.astype(int), 0]
            X = candidate[part.astype(int), 1]
            cordinates.append([X, Y])
    return np.array(cordinates).astype(int)


# This transforms the list of coordinates into an image
# This seems to be wrong?
# def cords_to_map(cords, img_size, sigma=6):
#     result = np.zeros(img_size + cords.shape[0:1], dtype='float32')
#     for i, point in enumerate(cords):
#         if point[0] == -1 or point[1] == -1:
#             continue
#         xx, yy = np.meshgrid(np.arange(img_size[1]), np.arange(img_size[0]))
#         result[..., i] = np.exp(-((yy - point[0]) ** 2 + (xx - point[1]) ** 2) / (2 * sigma ** 2))
#     return result

def cords_to_map(cords, img_size, sigma=6):
    result = np.zeros(img_size + cords.shape[0:1], dtype='float32')
    for i, point in enumerate(cords):
        if point[0] == -1 or point[1] == -1:
            continue
        xx, yy = np.meshgrid(np.arange(img_size[1]), np.arange(img_size[0]))
        result[..., i] = np.exp(-((yy - point[0]) ** 2 + (xx - point[1]) ** 2) / (2 * sigma ** 2))
    return result

def compute_pose_estimation(oriImg):
    # Set this parameters by default
    threshold = 0.1
    boxsize = 368
    scale_search = [0.5, 1, 1.5, 2]

    # Pre-process the image
    multiplier = [x * boxsize / oriImg.shape[0] for x in scale_search]

    heatmap_avg = np.zeros((oriImg.shape[0], oriImg.shape[1], 19))
    paf_avg = np.zeros((oriImg.shape[0], oriImg.shape[1], 38))

    for m in range(len(multiplier)):
        scale = multiplier[m]

        new_size = (np.array(oriImg.shape[:2]) * scale).astype(np.int32)
        imageToTest = resize(oriImg, new_size, order=3, preserve_range=True)

        imageToTest_padded = imageToTest[np.newaxis, :, :, :]/255 - 0.5
        # Resize the image to the size of the first network entry
        imageToProcess = st.resize(imageToTest_padded, (1, 368, 368), preserve_range=True, order=1)

        output1, output2 = model.predict(imageToProcess)

        heatmap = st.resize(output2[0], oriImg.shape[:2], preserve_range=True, order=1)
        paf = st.resize(output1[0], oriImg.shape[:2], preserve_range=True, order=1)
        heatmap_avg += heatmap
        paf_avg += paf

    heatmap_avg /= len(multiplier)


    # Compute the coordinates
    pose_cords = compute_cordinates(heatmap_avg, paf_avg, oriImg)

    # Compute pose map
    #pose_cords = np.concatenate([np.expand_dims(pose_cords[:, 1], -1), np.expand_dims(pose_cords[:, 0], -1)], axis=1)
    #img_size = (128, 64)
    img_size = oriImg.shape[:-1]
    pose_map = cords_to_map(pose_cords, img_size)


    # Obtain the final representation
    # What is the final representation of the pose?? Just the coordinates??
    # For now the representation is 128x64x18 (considering that the original image was 128x64)
    # Process the pose img
    pose_img = torch.from_numpy(pose_map).float()  # h, w, c
    pose_img = pose_img.permute(2, 0, 1)  # c, h, w
    pose_img = torch.unsqueeze(pose_img, 0)  # 1 x c x h x w

    return pose_img