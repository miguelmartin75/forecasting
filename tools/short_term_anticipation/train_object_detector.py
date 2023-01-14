from detectron2.utils.logger import setup_logger
setup_logger()

import os, sys
from detectron2 import model_zoo
from detectron2.config import get_cfg
from detectron2.data.datasets import register_coco_instances
from detectron2.engine import DefaultTrainer, default_argument_parser, default_setup, hooks, launch
from detectron2.evaluation import COCOEvaluator
from detectron2.data import DatasetCatalog, MetadataCatalog


bases = {
    'faster_rcnn' : {
        'R50_FPN_1x' : "COCO-Detection/faster_rcnn_R_50_FPN_1x.yaml",
        'R50_FPN_3x' : "COCO-Detection/faster_rcnn_R_50_FPN_3x.yaml",
        "R101_FPN_3x" : "COCO-Detection/faster_rcnn_R_101_FPN_3x.yaml"
    },
    'retinanet' : {
        'R50_FPN_1x' : "COCO-Detection/retinanet_R_50_FPN_1x.yaml"
    }
}

class MyTrainer(DefaultTrainer):
    @classmethod
    def build_evaluator(cls, cfg, dataset_name, output_folder=None):
        if output_folder is None:
            output_folder = os.path.join(cfg.OUTPUT_DIR,"inference")
        return COCOEvaluator(dataset_name, cfg, True, output_folder)

def main(args):
    register_coco_instances("ego4d_train", {}, args.path_to_train_json, args.path_to_images)
    register_coco_instances("ego4d_val", {}, args.path_to_val_json, args.path_to_images)

    data = DatasetCatalog.get("ego4d_train")
    metadata = MetadataCatalog.get("ego4d_train")
    # metadata.set("things_classes", json.load(open("things.json")))

    cfg = get_cfg()
    cfg.merge_from_file(model_zoo.get_config_file(bases[args.arch][args.base]))

    base_len = 15_000  # the length of the COCO dataset

    current_len = len(data) # the length of the loaded dataset
    num_classes = len(metadata.thing_classes)

    scale_factor = current_len/base_len # scale factor to adapt the learning schedule
    cfg.OUTPUT_DIR = str(args.output_dir)
    cfg.DATASETS.TRAIN = ("ego4d_train",)
    cfg.DATASETS.TEST = ("ego4d_val",)
    cfg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url(bases[args.arch][args.base]) 

    cfg.SOLVER.MAX_ITER = int(scale_factor*cfg.SOLVER.MAX_ITER) #adapt max iter
    cfg.SOLVER.STEPS = [int(scale_factor*x) for x in cfg.SOLVER.STEPS] #adapt steps

    cfg.SOLVER.CHECKPOINT_PERIOD = args.checkpoint_period
    cfg.TEST.EVAL_PERIOD = args.eval_period
    if args.arch=='faster_rcnn':
        cfg.MODEL.ROI_HEADS.NUM_CLASSES = num_classes
    else:
        cfg.MODEL.RETINANET.NUM_CLASSES = num_classes

    if args.base_lr is not None:
        cfg.SOLVER.BASE_LR = args.base_lr

    cfg.SOLVER.IMS_PER_BATCH = 8
    with open(os.path.join(args.output_dir, 'config.yaml'),'w') as f:
        f.write(cfg.dump())

    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    print("cfg=", cfg)
    trainer = MyTrainer(cfg)
    trainer.resume_or_load(resume=False)
    trainer.train()


def run_main(args):
    # main(args)
    launch(
        main,
        args.num_gpus,
        num_machines=1,
        machine_rank=0,
        dist_url=f'tcp://127.0.0.1:{args.port}',
        args=(args,)
    )


if __name__ == '__main__':
    print("please defer to scripts/run_obj_det.py", flush=True)
