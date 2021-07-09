import voxelbotutils as vbu
import discord
from discord.ext import commands
import asyncpg


class CommandManagement(vbu.Cog):

    @vbu.Cog.listener()
    async def on_command_error(self, ctx: vbu.Context, error: commands.CommandError):
        """
        Catches command not found errors and hopes that they're part of the guild's custom.
        """

        # Only handle commandnotfounds
        if not isinstance(error, commands.CommandNotFound):
            return

        # Grab the response from the database
        async with self.bot.database() as db:
            rows = await db(
                """SELECT * FROM custom_commands WHERE guild_id=$1 AND command_name=$2""",
                ctx.guild.id, ctx.invoked_with,
            )
        if not rows:
            return
        return await ctx.send(rows[0]['response'], wait=False)

    @vbu.command(argument_descriptions=(
        "The name of the command that you want to add.",
        "The description for the command that will show when you press /.",
        "The response that the command should output. Using '\\n' will result in a new line.",
    ))
    @commands.has_guild_permissions(manage_guild=True)
    @commands.guild_only()
    async def addcommand(self, ctx: vbu.Context, command_name: str, command_description: str, command_response: str):
        """
        Adds a command to your guild.
        """

        # See if the command name is valid
        if " " in command_name:
            return await ctx.send("You can't have spaces in your command name.", wait=False)
        if len(command_name) > 32:
            return await ctx.send("That command name is too long - it can be a maximum of 32 characters.")
        if command_name.lower() != command_name:
            return await ctx.send("Command names have to be entirely lowercase.")

        # Save the new command
        async with self.bot.database() as db:

            # Make sure it's unique
            try:
                await db(
                    """INSERT INTO custom_commands (guild_id, command_name, response, description) VALUES ($1, $2, $3, $4)""",
                    ctx.guild.id, command_name, command_response.replace("\\n", "\n"), command_description,
                )

            # It isn't unique
            except asyncpg.UniqueViolationError:
                return await ctx.send(
                    f"You already have a command with the name **{command_name}**! :<",
                    wait=False,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

            # Patch it into the guild
            command = vbu.ApplicationCommand(
                name=command_name,
                description=command_description,
            )
            created = await self.bot.create_guild_application_command(ctx.guild, command)
            await db(
                """UPDATE custom_commands SET command_id=$3 WHERE guild_id=$1 AND command_name=$2""",
                ctx.guild.id, command_name, created.id,
            )

        # Tell the user it's done
        return await ctx.send(
            f"Added your new custom command, **{command_name}**!",
            wait=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @vbu.command(argument_descriptions=(
        "The name of the command that you want to remove.",
    ))
    @commands.has_guild_permissions(manage_guild=True)
    @commands.guild_only()
    async def removecommand(self, ctx: vbu.Context, command_name: str):
        """
        Removes a command from your guild.
        """

        # Remove it from the database
        async with self.bot.database() as db:
            rows = await db(
                """DELETE FROM custom_commands WHERE guild_id=$1 AND command_name=$2 RETURNING *""",
                ctx.guild.id, command_name
            )

        # Turns out there was no command
        if not rows:
            return await ctx.send("You don't have a command with that name :<", wait=False)

        # Remove it as a slash command
        command = vbu.ApplicationCommand(None, None)
        command.id = rows[0]['command_id']
        await self.bot.delete_guild_application_command(ctx.guild, command)

        # Tell the user we're done
        return await ctx.send(
            f"Removed your custom command, **{command_name}**.",
            wait=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @vbu.command()
    @commands.guild_only()
    async def listcommands(self, ctx: vbu.Context):
        """
        Gives you a list of all the commands for the guild.
        """

        async with self.bot.database() as db:
            rows = await db("""SELECT * FROM custom_commands WHERE guild_id=$1""", ctx.guild.id)
        if not rows:
            return await ctx.send("There are no commands created for this guild yet.", wait=False)
        if len((output := "\n".join([f"\N{BULLET} **{i['command_name']}** (*{i['description'] or 'null'}*)" for i in rows]))) > 2_000:
            output = "\n".join([f"\N{BULLET} **{i['command_name']}**" for i in rows])
        return await ctx.send(output, wait=False, ephemeral=True)


def setup(bot: vbu.Bot):
    x = CommandManagement(bot)
    bot.add_cog(x)
