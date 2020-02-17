##Overview

This repository defines an [Slack Application](https://api.slack.com/start/overview), called the `Whistleblower Bot` that monitors all messages in certain list of channels for having a particular phrase embed in them.
Both the channels and phrases are set by users while interacting with a bot provided by the application.

##Slack application installation

If you need to create a separate Slack application that will have this module as the backend, then you should follow the guide to the apps linked above.

`Whistleblower Bot` relies on Slack Event API, thus the crucial is the task of enabling it on your app settings page.
In _Features -> Event Subscriptions_ toggle `Enable Events` on to enable Events API.
Next, register valid Request URL for Event API; the backend must respond properly to one time issued challenge request.
Add here the endpoint through which Slack API can reach the backend server.
(The challenge and all follow up event notification requests are processed properly by handler behind `/event-listener` relative URL path)
Add subscription to following event types under `Subscribe to bot events` section:
* app_mention
* message.im
* message.channels

Install the Slack app in any of worspaces available to you, when you do this you receive OAuth Access Token for your bot user.
This token must be then set as environment variable on the machine running `docker-compose`.

Now add *@whistleblower_bot* to any number of public channels.

**NOTE:** when you register request URL for Event API the backend application must be up and running, so that it could respond to the challenge request.

##Deploy application

**NOTE:** before starting the services `SLACK_API_TOKEN` environment variable must be set to the value of OAuth Access Token given to you when adding the bot user to the workspace.

Deploy the app by running `docker-compose up` from its root directory.

**NOTE:** it is up to you to provide connectivity to and from the Internet to your application, so that both Slack Event API executors could reach the backend and that it could in turn make request to Slack Web API.

**HINT:** if you are developing locally, you can use [ngrok](https://ngrok.com/) or service with similar functionality to get a tunnel for your app.

##Development

###Architecture overview

Conceptually the application consists of four components:
* HTTP web server - handling incoming requests from Slack Event API;
* asynchronous execution backend - processes incoming events in asynchronous matter, according to [Event API guide](https://api.slack.com/events-api#tips)
* task queue - for asynchronous communication between the server and async backend, where the latter subscribes to messages from the former.
* external configuration storage - to accommodate concurrent access to the same piece of data.

Web server is a simple app implemented using Flask framework, that accepts any incoming request and immediately issues an asynchronous task, returning 200 'OK'.
The task is then picked up by any number of [Celery](https://docs.celeryproject.org/en/latest/index.html) wrapped workers with custom logic.
Since multiple workers may be retrieving or updating a singular piece of information - the user configuration, external storage service is there to facilitate this.
[Redis](https://redis.io/) is used as both configuration storage and message queue.

In current version `docker-compose` fires up three containers: server app, redis and celery worker node.

###Dev setup

Unfortunately right now the default deployment option, via `docker-compose`, is not very dev friendly, i.e. one has to rebuild the containers every time the code changes, both server and celery workers are deployed w/o logging enabling.

If you want to develop quickly and debug issue in more easy way, I suggest you fire up the server and async worker backend locally, maybe even with disabled concurrency.

##Further plans

* add test coverage
* provide dev setup
* (UPD)
