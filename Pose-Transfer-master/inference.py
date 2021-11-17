import os
from options.test_options import TestOptions
from data_processing.data_loader import CreateDataLoader
from models.models import create_model
from tool.compute_coordinates_inference import compute_pose_estimation
from util.visualizer import Visualizer
from skimage.io import imread
import matplotlib.pyplot as plt
import torch
import util.util as util
from data_processing.base_dataset import BaseDataset, get_transform
from PIL import Image


# Prepare the options
def set_options_inference():
    opt = TestOptions(norm='batch', how_many=20, BP_input_nc=18, dataroot='./market_data/',
                      name='market_PATN', nThreads=1, model='PATN', phase='test', dataset_mode='keypoint', batchSize=1,
                      serial_batches=True, no_flip=True, checkpoints_dir='./checkpoints', which_model_netG='PATN',
                      pairLst='./market_data/market-pairs-test.csv', results_dir='./results', resize_or_crop='no', which_epoch='latest', display_id=0)
    return opt

def load_img(input_path, transform):
    # Load the original image
    oriImg = imread(input_path)[:,:, ::-1]# B,G,R order
    # Create its pose estimation
    img_name = input_path.split('/')[-1]

    pose_map = compute_pose_estimation(oriImg, img_name)

    # What is the final representation of the pose?? Just the coordinates??
    # For now the representation is 128x64x18 (considering that the original image was 128x64)
    # Process the pose img
    pose_img = torch.from_numpy(pose_map).float()  # h, w, c
    pose_img = pose_img.permute(2, 0, 1)    # c, h, w
    pose_img = torch.unsqueeze(pose_img, 0) # 1 x c x h x w

    # How do we generate a random pose??

    # Plot the pose of the image
    #aux = util.draw_pose_from_map(pose_img)[0]
    #plt.imshow(aux)
    #plt.show()


    # Reshape the original image into 1 x 3 x 128 x 64 (from 1 x 128 x 64 x 3)
    P1 = Image.open(input_path).convert('RGB')
    P1 = transform(P1.copy())
    P1 = torch.unsqueeze(P1, 0)

    # Show the original image with the transformation
    #aux = util.tensor2im(P1)
    #plt.imshow(aux)
    #plt.show()

    return P1, pose_img, pose_img

# Provide the input image 1, the pose of image 1, and the pose of the new image
# Format: P1 image has shape torch.Size([1,3,128,64]) IMPORTANT!!
# BP1 has shape [1, 18,128, 64]. So it has 18 channels (Check how to generate this)
def process_image(opt, image1, pose1, pose2):
    # Load the model
    model = create_model(opt)
    model = model.eval()

    # Create the visualizer
    visualizer = Visualizer(opt)

    # Create the output_path (CHANGE THIS ONE)
    output_path = os.path.join(opt.results_dir, opt.name, '%s_%s' % (opt.phase, opt.which_epoch))

    # Predict the new image
    final_image = model.predict(image1, pose1, pose2)

    # Transform it to an image
    final_image = util.tensor2im(final_image.data)
    #plt.imshow(final_image.data)
    #plt.show()

    i = 0
    visualizer.save_images_custom(output_path, i, final_image)



# RUN: python inference.py
if __name__ == '__main__':
    # Prepare the training options
    opt = set_options_inference()
    transform = get_transform(opt)

    # read the corresponding images
    img_path = os.path.abspath('./test_inference_img/0002_c1s1_000451_03.jpg')
    output_path = os.path.abspath('./')
    img1, pose1, pose2 = load_img(img_path, transform)

    # process the images
    process_image(opt=opt, image1=img1, pose1=pose1, pose2=pose2)
