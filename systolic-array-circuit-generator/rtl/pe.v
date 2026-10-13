`timescale 1ns/1ps
// One unsigned multiply-accumulate processing element.
module pe #(
    parameter integer DATA_WIDTH = 8,
    parameter integer ACC_WIDTH  = 20
) (
    input wire clk,
    input wire rst,
    input wire [DATA_WIDTH-1:0] a_in,
    input wire [DATA_WIDTH-1:0] b_in,
    output reg [DATA_WIDTH-1:0] a_out,
    output reg [DATA_WIDTH-1:0] b_out,
    input wire clear_acc,
    output reg [ACC_WIDTH-1:0] acc
);
    wire [2*DATA_WIDTH-1:0] product;
    assign product = a_in * b_in;

    always @(posedge clk) begin
        if (rst) begin
            a_out <= {DATA_WIDTH{1'b0}};
            b_out <= {DATA_WIDTH{1'b0}};
            acc   <= {ACC_WIDTH{1'b0}};
        end else begin
            a_out <= a_in;
            b_out <= b_in;
            if (clear_acc)
                acc <= {ACC_WIDTH{1'b0}};
            else
                acc <= acc + product;
        end
    end
endmodule
