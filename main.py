from segmentation.src.utils import create_model, process_image, bbox_per_person
import human_body_generation.auxiliary_functions as human_body_generation
import matplotlib.pyplot as plt
import os
import numpy as np
import sys
sys.path.append('./human_body_generation')

# This file attempts to create the final pipeline for the project "Object substitution in RGB images"


# Create the segmentation model
seg_model = create_model()

# Define the input path
#img_path = os.path.abspath('./segmentation/input/image1.jpg')
img_path = os.path.abspath('./human_body_generation/test_inference_img/0002_c1s1_000551_01.jpg')
threshold = 0.9#0.965

# Segment the image
orig_image, masks, boxes, labels = process_image(image_path=img_path, threshold=threshold, model= seg_model)

# Produce the new image in-painted by calling module 2


# Created the zoomed image for each of the human bodies in the image
person_images = bbox_per_person(orig_image, boxes, labels)

# Create the new image for each of the detected human bodies
new_images = []

# This is the final image with all the people masked out (on which we will paste the new images)
output_image = None

# Discard the first one since it contains the full image
for person_img in person_images:
    plt.imshow(person_img.data)
    plt.show()
    person_img = np.asarray(person_img.data)

    # Problem: The new pose may not be of the size as the new image. Thus, we need to reshape it!!
    output_img = human_body_generation.compute_new_image(person_img)
    plt.imshow(output_img)
    plt.show()
    new_images.append(output_img)


    # Segmentation of the newly generated person
    mask = None


    # Fuse the new person into the output image (with all the people segemented out)
    # Basically, for now, paste the new person in its original bounding box


# Do the final impainting
