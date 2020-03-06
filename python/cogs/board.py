"""
This is a cog for a discord.py bot.

It provides commands for users to submit posts
to a board; board admins can then approve these
posts. Once approved, the bot allows for messages
to be anonymously responded to via direct
messages to Felix bot. Post messages can be
multi-line and contain formatting.

Commands:
    post
     ├ create <post id> <message>           Creates a post sent for approval
     ├ approve <post id> <message>          Admin only: approve a post
     ├ reply <post id or post_reply id>     Reply to a post
     └ close <post id> <optional message>   close a post, message optional
                                            aliases: reject, decline
"""

import asyncio
import json
import time
from collections import deque
from discord.ext import commands
from discord import Member, Embed
import string
import random

class Board(commands.Cog, name="Board"):
    def __init__(self, client):
        self.client = client
        self.board_roles = self.client.config['board_roles']
        self.BOARD_CHANNEL = self.client.config['board_channel']

    def load_state(self):
        with open("../state.json", "r") as statefile:
            return json.load(statefile)
    def save_state(self, state):
        with open("../state.json", "w") as statefile:
            return json.dump(state, statefile, indent=1)
    def random_string_id(self):
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for x in range(6))
    def find_user(self, user_id):
        for user in self.client.users:
            if user.id == user_id:
                return user
        return False
    
    @commands.group(
        name="post",
        invoke_without_command=True,
        aliases=[]
    )
    async def post(self, ctx):
        """PLEASE USE IN DIRECT MESSAGE TO REMAIN ANONYMOUS!"""
        await ctx.send_help('post')

    @post.command(
        name='create',
        aliases=[],
        hidden=False,
    )
    async def create(self, ctx, *, post_message):
        """
            `felix post create <message>`: Post a new message, which can have formatting / line breaks.
        """
        await ctx.send("Starting post...")
        state = self.load_state()
        posts = state.get('posts', {})
        post_id = self.random_string_id()
        posts[post_id] = {
            'poster': ctx.author.id,
            'message': post_message,
            'color': "",
            'replies': {},
            'approved': False,
        }
        state['posts'] = posts
        self.save_state(state)
        for user in self.client.users:
            if user.id in self.board_roles:
                embed = Embed(
                    title="to approve type `felix post approve "+ post_id + "` or decline with `felix post close " + post_id +"`",
                    description=post_message,
                    # color=posts[post_id].color,
                    color=0xFF0000
                )
                await user.send('New Post Awaiting Approval!', embed=embed)
                break
        await ctx.send("Post submitted for approval.")

    @post.command(
        name='close',
        aliases=['reject', 'decline'],
        hidden=False,
    )
    async def close(self, ctx, *, post_close_payload):
        """
            `felix post close <post_id>`: Close post by ID, can only be done by author or admin
        """
        await ctx.send("Closing post...")
        close_message = None
        post_id = post_close_payload
        if ' ' in post_close_payload:
            (post_id, close_message) = post_close_payload.split(" ", 1)

        state = self.load_state()
        posts = state.get('posts', {})
        if post_id not in posts.keys():
            await ctx.send("No post found with that ID")
            return
        if ctx.author.id not in self.board_roles and ctx.author.id != posts[post_id]['poster']:
            await ctx.send("You do not have permission to close this post.")
            return
        embed = Embed(
            title='Post ' + post_id + ' has been closed',
            description=close_message,
            # color=posts[post_id].color,
            color=0xFF0000
        )
        if posts[post_id]['approved']:
            # public message about closure
            target = self.client.get_channel(self.BOARD_CHANNEL)
        else:
            # message just to original poster
            target = self.find_user(posts[post_id]['poster'])
        await ctx.send("Closure Message preview:", embed=embed)
        del posts[post_id]
        state['posts'] = posts
        self.save_state(state)
        await ctx.send("Posting closure message...")
        await target.send('Post closed!', embed=embed)

    @post.command(
        name='approve',
        aliases=[],
        hidden=False,
    )
    async def approve(self, ctx, *, post_id):
        """
            `felix post approve <post id>`: Admin only command for approving posts.
        """
        await ctx.send("Parsing approval request...")
        state = self.load_state()
        posts = state.get('posts', {})
        if post_id not in posts.keys():
            return await ctx.send("No post found with that ID")
            return
        await ctx.send("Preparing post for channel...")
        target = self.client.get_channel(self.BOARD_CHANNEL)
        embed = Embed(
            title='To reply, message Felix with `felix post reply ' + post_id + '` followed by your message',
            description=posts[post_id]['message'],
            # color=posts[post_id].color,
            color=0xFF0000
        )
        await ctx.send("Post preview:", embed=embed)
        posts[post_id]['approved'] = True
        state['posts'] = posts
        self.save_state(state)
        await ctx.send("Posting...")
        await target.send('New Announcement!', embed=embed)
        await ctx.send("Check announcement channel for post.")
    @post.command(
        name='reply',
        aliases=[],
        hidden=False,
    )
    async def reply(self, ctx, *, post_reply_payload):
        """
            `felix post reply <reply_id> <message>`: Reply to a post with the specified ID.
        """
        state = self.load_state()
        posts = state.get('posts', {})
        reply_id = None
        post_id = None
        if ' ' not in post_reply_payload:
            await ctx.send("Please provide reply message")
            return
        (post_reply_id, post_message) = post_reply_payload.split(" ", 1)
        if '_' in post_reply_id:
            (post_id, reply_id) = post_reply_id.split("_")
        else:
            post_id = post_reply_id
        if post_id not in posts.keys():
            await ctx.send("No post found with that ID")
            return
        if ctx.author.id == posts[post_id]['poster']:
            # OP is replying to a user
            if reply_id is None:
                await ctx.send("Please specify post and reply ID as `<postID>_<replyID>`. You can't reply to your own post with just the post ID.")
                return
            #crash
            recipient = self.find_user(posts[post_id]['replies'][reply_id])
            reply_title = 'To reply, message Felix with `felix post reply ' + post_id + '` followed by your message'
        else:
            if reply_id is None:
                # Look up reply for user if exists
                for r_id in posts[post_id]['replies'].keys():
                    if posts[post_id]['replies'][r_id] == ctx.author.id:
                        reply_id = r_id
                        break
            if reply_id is None:
                reply_id = self.random_string_id()
                posts[post_id]['replies'][reply_id] = ctx.author.id
            recipient = self.find_user(posts[post_id]['poster'])
            reply_title = 'To reply, message Felix with `felix post reply ' + post_id + '_' + reply_id + '` followed by your message'
        state['posts'] = posts
        self.save_state(state)
        embed = Embed(
            title=reply_title,
            description=post_message,
            # color=posts[post_id].color,
            color=0xFF0000
        )
        await recipient.send("New reply to post " + post_reply_id, embed=embed)

def setup(client):
    """This is called when the cog is loaded via load_extension"""
    client.add_cog(Board(client))
