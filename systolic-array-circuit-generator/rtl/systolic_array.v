`timescale 1ns/1ps
// Rectangular unsigned systolic MAC array.
// Packed inputs: a_in has one DATA_WIDTH slice per row; b_in has one
// DATA_WIDTH slice per column. Accumulators are packed in row-major order.
// A moves right; B moves down. Each PE accumulates its current product each cycle.
module systolic_array #(
    parameter integer ROWS       = 2,
    parameter integer COLS       = 2,
    parameter integer DATA_WIDTH = 8,
    parameter integer ACC_WIDTH  = 20
) (
    input wire clk,
    input wire rst,
    input wire clear_acc,
    input wire [ROWS*DATA_WIDTH-1:0] a_in,
    input wire [COLS*DATA_WIDTH-1:0] b_in,
    output wire [ROWS*COLS*ACC_WIDTH-1:0] acc_out
);
    wire [DATA_WIDTH-1:0] a_bus [0:ROWS-1][0:COLS];
    wire [DATA_WIDTH-1:0] b_bus [0:ROWS][0:COLS-1];
    wire [ACC_WIDTH-1:0] acc_bus [0:ROWS-1][0:COLS-1];

    genvar r, c;
    generate
        for (r = 0; r < ROWS; r = r + 1) begin : GEN_A_INPUT
            assign a_bus[r][0] = a_in[r*DATA_WIDTH +: DATA_WIDTH];
        end
        for (c = 0; c < COLS; c = c + 1) begin : GEN_B_INPUT
            assign b_bus[0][c] = b_in[c*DATA_WIDTH +: DATA_WIDTH];
        end
        for (r = 0; r < ROWS; r = r + 1) begin : GEN_ROW
            for (c = 0; c < COLS; c = c + 1) begin : GEN_COL
                pe #(.DATA_WIDTH(DATA_WIDTH), .ACC_WIDTH(ACC_WIDTH)) u_pe (
                    .clk(clk), .rst(rst),
                    .a_in(a_bus[r][c]), .b_in(b_bus[r][c]),
                    .a_out(a_bus[r][c+1]), .b_out(b_bus[r+1][c]),
                    .clear_acc(clear_acc), .acc(acc_bus[r][c])
                );
                assign acc_out[(r*COLS+c)*ACC_WIDTH +: ACC_WIDTH] = acc_bus[r][c];
            end
        end
    endgenerate
endmodule
