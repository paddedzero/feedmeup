---
layout: default
title: Home
---

Welcome to the Weekly News Brief!  

Here I attempt to distill news on Cybersecurity, Cloud, AI and Regulatory News.

<ul class="brief-list">
  {% for post in site.posts %}
    <li>
      <a href="{{ post.url | relative_url }}">
        {{ post.title }}
      </a>
      - <span>{{ post.date | date: "%B %d, %Y" }}</span>
    </li>
  {% endfor %}
</ul>

<hr class="post-separator">

{% for post in site.posts reversed %}
  <article class="post">
    <h2>{{ post.title }}</h2>
    <p class="post-meta"><em>{{ post.date | date: "%B %d, %Y" }}</em></p>
      Shareable : <a href="{{ post.url | relative_url }}">
        {{ post.title }} - <span>{{ post.date | date: "%B %d, %Y" }}</span>
      </a>

    {{ post.content }}
  </article>

  {% unless forloop.last %}
    <hr class="post-separator">
  {% endunless %}
{% endfor %}