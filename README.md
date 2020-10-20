<div align="center" markdown> 

<img src="https://i.imgur.com/BnuiQOg.png"/>

# Convert Class Shape
  
<p align="center">

  <a href="#Overview">Overview</a> •
  <a href="#How-To-Run">How To Run</a> •
  <a href="#Explanation">Explanation</a>
</p>

[![](https://img.shields.io/badge/slack-chat-green.svg?logo=slack)](https://supervise.ly/slack) 
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/supervisely-ecosystem/convert-class-shape)
[![views](https://dev.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/convert-class-shape&counter=views&label=views)](https://supervise.ly)
[![used by teams](https://dev.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/convert-class-shape&counter=runs&label=used%20by%20teams)](https://supervise.ly)
[![runs](https://dev.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/convert-class-shape&counter=downloads&label=runs&123)](https://supervise.ly)

</div>

## Overview 
sdasdad


## How To Run

### Step 1: Run from context menu of project / dataset

Go to "Context Menu" (images project or dataset) -> "Run App" -> "Transform" -> "Unpack AnyShape Classes"

<img src="https://i.imgur.com/r8AlpZC.png" width="600"/>

### Step 2:  Waiting until the task finishes

Once app is started, new task appear in workspace tasks. Monitor progress from "Tasks" list.

<img src="https://i.imgur.com/JqHh9pZ.png"/>

## Explanation
    
- Result project name = original name + "(new shapes)" suffix

- Your data is safe: app creates new project with modified classes and objects. The original project remains unchanged

- Before converting `AnyShape` classes, you have to unpack it with another app - [Unpack Anyshape](https://github.com/supervisely-ecosystem/unpack-anyshape) 

- Colors of new classes will be generated randomly

- Note: transformation from raster (bitmap) to vector (polygon) will result in huge number of points. App performs approximation to reduce the number. That can lead to slight loss of accuracy at borders. Special settings to control approximation will be released in next version.
