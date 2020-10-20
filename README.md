<div align="center" markdown> 

<img src="https://i.imgur.com/BnuiQOg.png"/>

# Convert Class Shape
  
<p align="center">

  <a href="#Overview">Overview</a> •
  <a href="#How-To-Run">How To Run</a> •
  <a href="#Explanation">Explanation</a>
</p>

[![](https://img.shields.io/badge/slack-chat-green.svg?logo=slack)](https://supervise.ly/slack) 
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/supervisely-ecosystem/unpack-anyshape)
[![views](https://dev.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/unpack-anyshape&counter=views&label=views)](https://supervise.ly)
[![used by teams](https://dev.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/unpack-anyshape&counter=runs&label=used%20by%20teams)](https://supervise.ly)
[![runs](https://dev.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/unpack-anyshape&counter=downloads&label=runs&123)](https://supervise.ly)

</div>

## Overview 

In Supervisely, you have to define classes before labeling. The shape of class specifies instruments that are available in annotation interface. For example, if you need to label cars with polygonal tool, you have to create class `Car` with shape `Polygon`.

Supervisely supports the following shapes:
- Rectangle
- Polygon
- Bitmap
- Line (polyline)
- Point
- Keypoints (graphs) - sets of vertices connected by edges
- Cuboids (2D and 3D)
- AnyShape (will be explained below)
- ...

Example: objects of class `Bitmap` can be labeled with the following instruments: brush + eraser, pen, polygon, SmartTool. Whatever instrument is used, these objects always are saved as masks (raster). 

### What is AnyShape class? 

Let's concider the following case: semantic segmentation of cars. You would like to label cars faster with SmartTool (NN that integrated to labeling interface and produces masks). If SmartTool produces inaccurate predictions you will label objects manually with Polygonal tool. So, you want to label objects of class `car` with absolutely different instruments: Polygonal tool (vector) and SmartTool (raster). How to do it?

**First option**: Create two separate classes: `car_bitmap` with shape `Bitmap` and `car_polygon` with shape `Polygon`. Thus SmartTool objects will be of class `car_bitmap` and polygonal objects will be of class `car_polygon`. The main drawback: this approach doubles up the number of classes and later (before NN training) you have to merge class pairs to a single one anyway. And what if you have tens or even hundreds of classes?

**Second option**: Create class `car` with shape `AnyShape`. It means that you can use all annotation instruments to label objects. The main drawback: your labeling team have to understand annotation requirements well. For example, if labelers are not restricted to specific instrument, you expect polygons but they can label objects with rectangles. `¯\_(ツ)_/¯`


## How To Run

### Step 1: Run from context menu of project / dataset

Go to "Context Menu" (images project or dataset) -> "Run App" -> "Transform" -> "Unpack AnyShape Classes"

<img src="https://i.imgur.com/r8AlpZC.png" width="600"/>

### Step 2:  Waiting until the task finishes

Once app is started, new task appear in workspace tasks. Monitor progress from "Tasks" list.

<img src="https://i.imgur.com/JqHh9pZ.png"/>

## Explanation

- Result project name = original name + "(without AnyShape)" suffix

- Your data is safe: app creates new project with modified classes and objects. The original project remains unchanged

- All "AnyShape" classes will be unpacked to equivalent classes with strictly defined shapes. In our example the class `car` will be splited to classes `car_polygon`, `car_bitmap`, `car_rectangle`. 

- Colors of new classes will be generated randomly
